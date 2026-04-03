"""
Combine on-page crawl signals with DataForSEO Labs ranked_keywords for the domain
into topic clusters (what the site says vs what search engines rank it for).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

# Tokens shorter than this are ignored for matching (except we still allow 3-char if in seed)
_MIN_TOKEN_LEN = 3

_STOP = frozenset({
    "the", "and", "for", "with", "your", "from", "this", "that", "are", "was", "has", "have",
    "will", "can", "you", "not", "all", "any", "our", "but", "its", "it's", "their", "they",
    "what", "when", "where", "which", "who", "how", "why", "into", "about", "more", "some",
    "than", "then", "them", "these", "those", "also", "just", "like", "here", "there", "very",
    "each", "other", "such", "only", "same", "over", "after", "before", "between", "through",
    "using", "use", "used", "new", "get", "got", "may", "way", "make", "made", "most", "many",
    "home", "page", "site", "web", "www", "com", "online", "free", "best", "top", "click",
})


def tokenize(text: str) -> Set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-z0-9][a-z0-9-]*", text.lower())
    return {w for w in words if len(w) >= _MIN_TOKEN_LEN and w not in _STOP}


def _normalize_ranked_row(item: Dict[str, Any]) -> Dict[str, Any] | None:
    keyword_data = item.get("keyword_data") or {}
    kw = (keyword_data.get("keyword") or item.get("keyword") or "").strip()
    if not kw:
        return None
    ki = keyword_data.get("keyword_info") or {}
    try:
        sv = int(
            ki.get("search_volume")
            or ki.get("search_volume_global")
            or ki.get("sum_search_volume")
            or item.get("search_volume")
            or item.get("sum_search_volume")
            or 0,
        )
    except (TypeError, ValueError):
        sv = 0
    ra = item.get("rank_absolute")
    if ra is None:
        ra = item.get("rank")
    rg = item.get("rank_group")
    try:
        rank = int(ra) if ra is not None else None
    except (TypeError, ValueError):
        rank = None
    try:
        rank_g = int(rg) if rg is not None else None
    except (TypeError, ValueError):
        rank_g = None
    return {
        "keyword": kw,
        "search_volume": sv,
        "rank": rank,
        "rank_group": rank_g,
    }


def extract_crawl_topic_seeds(extracted_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build topic seeds from crawl fields (headings, FAQs, candidates).
    Each seed: label, tokens, sources (traceability).
    """
    seeds: List[Dict[str, Any]] = []
    for p in extracted_pages:
        url = str(p.get("url") or "")[:500]
        h1 = (p.get("h1") or "").strip()
        if h1:
            seeds.append(
                {
                    "label": h1[:200],
                    "tokens": sorted(tokenize(h1)),
                    "sources": [f"h1:{url}"],
                },
            )
        for h in p.get("h2_h3_headings") or []:
            text = str(h)
            if ":" in text:
                text = text.split(":", 1)[-1].strip()
            if len(text) >= 4:
                seeds.append(
                    {
                        "label": text[:200],
                        "tokens": sorted(tokenize(text)),
                        "sources": [f"heading:{url}"],
                    },
                )
        for fq in (p.get("faq_questions") or [])[:8]:
            fq = str(fq).strip()
            if len(fq) >= 8:
                seeds.append(
                    {
                        "label": fq[:200],
                        "tokens": sorted(tokenize(fq)),
                        "sources": [f"faq:{url}"],
                    },
                )
        for pk in (p.get("primary_keyword_candidates") or [])[:6]:
            pk = str(pk).strip()
            if len(pk) >= 3:
                seeds.append(
                    {
                        "label": pk[:120],
                        "tokens": sorted(tokenize(pk)),
                        "sources": [f"candidate:{url}"],
                    },
                )
    return _merge_overlapping_seeds(seeds)


def _merge_overlapping_seeds(seeds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedupe by token set; drop seeds that are strict subsets of a broader kept seed."""
    by_frozen: Dict[frozenset, Dict[str, Any]] = {}
    for s in seeds:
        tset = frozenset(s.get("tokens") or [])
        if not tset:
            continue
        if tset not in by_frozen:
            by_frozen[tset] = {
                "label": s["label"],
                "tokens": sorted(tset),
                "sources": list(s.get("sources") or []),
            }
        else:
            by_frozen[tset]["sources"].extend(s.get("sources") or [])
    items = list(by_frozen.values())
    items.sort(key=lambda x: -len(x["tokens"]))
    kept: List[Dict[str, Any]] = []
    for it in items:
        ts = set(it["tokens"])
        if any(ts <= set(k["tokens"]) and ts != set(k["tokens"]) for k in kept):
            continue
        kept = [k for k in kept if not (set(k["tokens"]) < ts)]
        kept.append(it)
    return kept[:40]


def _best_seed_for_keyword(
    kw_tokens: Set[str],
    seeds: List[Dict[str, Any]],
) -> Tuple[int | None, float]:
    if not kw_tokens or not seeds:
        return None, 0.0
    best_i: int | None = None
    best_score = 0.0
    for i, seed in enumerate(seeds):
        st = set(seed.get("tokens") or [])
        if not st:
            continue
        inter = len(kw_tokens & st)
        if inter == 0:
            continue
        union = len(kw_tokens | st) or 1
        jacc = inter / union
        overlap_ratio = inter / min(len(kw_tokens), len(st) or 1)
        score = max(jacc, overlap_ratio * 0.85)
        if score > best_score:
            best_score = score
            best_i = i
    return best_i, best_score


def build_topic_clusters(
    extracted_pages: List[Dict[str, Any]],
    ranked_items: List[Dict[str, Any]],
    *,
    match_threshold: float = 0.12,
) -> Dict[str, Any]:
    """
    Match Labs ranked keywords to crawl-derived seeds; leftovers go to unclustered.
    """
    seeds = extract_crawl_topic_seeds(extracted_pages)
    ranked_norm: List[Dict[str, Any]] = []
    for it in ranked_items:
        row = _normalize_ranked_row(it)
        if row:
            ranked_norm.append(row)

    clusters: List[Dict[str, Any]] = [
        {
            "topic_label": s["label"],
            "seed_tokens": s["tokens"],
            "seed_sources": s["sources"],
            "ranked_keywords": [],
            "total_search_volume": 0,
        }
        for s in seeds
    ]
    unclustered: List[Dict[str, Any]] = []

    for row in ranked_norm:
        kt = tokenize(row["keyword"])
        idx, score = _best_seed_for_keyword(kt, seeds)
        if idx is not None and score >= match_threshold:
            clusters[idx]["ranked_keywords"].append(row)
            clusters[idx]["total_search_volume"] += int(row.get("search_volume") or 0)
        else:
            unclustered.append(row)

    clusters.sort(key=lambda c: -int(c.get("total_search_volume") or 0))
    for c in clusters:
        c["ranked_keywords"].sort(
            key=lambda r: (
                r.get("rank") is None,
                r.get("rank") or 9999,
                -int(r.get("search_volume") or 0),
            ),
        )

    unclustered.sort(key=lambda r: (-int(r.get("search_volume") or 0), r.get("keyword") or ""))

    cluster_payload = [
        {
            "topic_label": c["topic_label"],
            "seed_sources": c["seed_sources"],
            "seed_tokens": c["seed_tokens"],
            "ranked_keywords": c["ranked_keywords"],
            "total_search_volume": c["total_search_volume"],
            "matched_keyword_count": len(c["ranked_keywords"]),
        }
        for c in clusters
        if c["ranked_keywords"]
    ]
    return {
        "crawl_topic_seeds": seeds,
        "topic_clusters": {
            "clusters": cluster_payload,
            "unclustered_ranked_keywords": unclustered,
            "stats": {
                "seed_count": len(seeds),
                "ranked_keyword_count": len(ranked_norm),
                "cluster_count": len(cluster_payload),
                "unclustered_count": len(unclustered),
            },
        },
        "ranked_keywords_normalized": ranked_norm,
    }


def compact_ranked_for_storage(ranked_norm: List[Dict[str, Any]], cap: int = 50) -> List[Dict[str, Any]]:
    """Persist a stable, bounded list for the crawl record."""
    rows = list(ranked_norm)
    rows.sort(
        key=lambda r: (
            r.get("rank") is None,
            r.get("rank") or 9999,
            -int(r.get("search_volume") or 0),
        ),
    )
    return rows[:cap]
