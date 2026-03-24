"""
Aggregate SEO metric helpers (location-mode aware).

Keeps serializers and views free of merge / comparison math. Does not touch
Labs enrichment or keyword generation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

SEO_LOCATION_MODE_LOCAL = "local"


def _positive_rank(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def effective_rank_for_aggregate_metrics(row: Optional[Dict[str, Any]], *, seo_location_mode: str) -> Optional[int]:
    """
    Rank used for snapshot-level aggregates (visibility, CTR traffic, counts).

    - organic (default): Labs/baseline ``rank`` only.
    - local: ``local_verified_rank`` when present and > 0, else baseline ``rank``.
    """
    row = row or {}
    baseline = _positive_rank(row.get("rank"))
    if str(seo_location_mode or "organic") != SEO_LOCATION_MODE_LOCAL:
        return baseline
    verified = _positive_rank(row.get("local_verified_rank"))
    if verified is not None:
        return verified
    return baseline


def local_verification_affects_visibility(
    *,
    seo_location_mode: str,
    baseline_metrics: Dict[str, Any],
    local_mode_metrics: Dict[str, Any],
) -> bool:
    """
    True when local-mode aggregates differ from baseline-rank aggregates in visibility inputs.

    Only meaningful when profile mode is local; callers should pass organic-style vs local-style
    ``recompute_snapshot_metrics_from_keywords`` results.
    """
    if str(seo_location_mode or "organic") != SEO_LOCATION_MODE_LOCAL:
        return False
    a = int(baseline_metrics.get("search_visibility_percent") or 0)
    b = int(local_mode_metrics.get("search_visibility_percent") or 0)
    if a != b:
        return True
    ap = int(baseline_metrics.get("estimated_search_appearances_monthly") or 0)
    bp = int(local_mode_metrics.get("estimated_search_appearances_monthly") or 0)
    return ap != bp


def build_seo_snapshot_api_metadata(
    *,
    seo_location_label: str,
    local_verified_keyword_count: int,
    local_verification_affects_visibility: bool,
) -> Dict[str, Any]:
    """Flat metadata dict merged into SEO API payloads (mode is set on the response separately)."""
    return {
        "seo_location_label": str(seo_location_label or ""),
        "local_verified_keyword_count": max(0, int(local_verified_keyword_count or 0)),
        "local_verification_affects_visibility": bool(local_verification_affects_visibility),
    }
