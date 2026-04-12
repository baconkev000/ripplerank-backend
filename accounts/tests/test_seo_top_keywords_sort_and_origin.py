"""Sort order and keyword_origin for persisted SEO top_keywords."""

import pytest

from accounts.dataforseo_utils import sort_top_keywords_for_display


def test_sort_top_keywords_ranked_before_unranked_then_volume():
    rows = [
        {"keyword": "c", "search_volume": 100, "rank": None, "local_verified_rank": None},
        {"keyword": "a", "search_volume": 50, "rank": 10, "local_verified_rank": None},
        {"keyword": "b", "search_volume": 200, "rank": 3, "local_verified_rank": None},
        {"keyword": "d", "search_volume": 300, "rank": None, "local_verified_rank": None},
    ]
    out = sort_top_keywords_for_display(rows)
    assert [r["keyword"] for r in out] == ["b", "a", "d", "c"]


def test_sort_top_keywords_uses_local_verified_when_rank_missing():
    rows = [
        {"keyword": "x", "search_volume": 100, "rank": None, "local_verified_rank": 5},
        {"keyword": "y", "search_volume": 500, "rank": None, "local_verified_rank": None},
    ]
    out = sort_top_keywords_for_display(rows)
    assert [r["keyword"] for r in out] == ["x", "y"]


def test_sort_top_keywords_max_rows_cap():
    rows = [{"keyword": f"k{i}", "search_volume": 100 - i, "rank": i + 1} for i in range(5)]
    out = sort_top_keywords_for_display(rows, max_rows=2)
    assert len(out) == 2


def test_keyword_origin_gap_semantics_in_enrich(monkeypatch):
    """New gap-appended rows carry keyword_origin gap (integration via enrich_with_gap_keywords)."""
    from accounts.dataforseo_utils import enrich_with_gap_keywords

    monkeypatch.setattr(
        "accounts.dataforseo_utils.get_competitors_for_domain_intersection",
        lambda **kwargs: {"filtered_competitors_used": ["competitor.example.com"]},
    )
    monkeypatch.setattr(
        "accounts.dataforseo_utils.get_keyword_gap_keywords",
        lambda *a, **kw: [
            {
                "keyword": "gap only phrase",
                "search_volume": 1200,
                "your_rank": None,
                "top_competitor": "OtherCo",
                "top_competitor_domain": "other.com",
                "top_competitor_rank": 2,
                "competitors": [{"domain": "other.com", "rank": 2}],
            }
        ],
    )

    user = object()
    tk: list[dict] = []
    enrich_with_gap_keywords(
        "mybrand.com",
        2840,
        "en",
        user,
        tk,
    )
    assert len(tk) == 1
    assert tk[0].get("keyword_origin") == "gap"
    assert tk[0].get("keyword") == "gap only phrase"
