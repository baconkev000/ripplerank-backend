import pytest

from accounts.dataforseo_utils import recompute_snapshot_metrics_from_keywords
from accounts.seo_metrics_service import local_verification_affects_visibility


@pytest.mark.django_db
def test_missed_equals_total_minus_appearances():
    metrics = recompute_snapshot_metrics_from_keywords(
        top_keywords=[
            {"keyword": "k1", "search_volume": 1000, "rank": 4},
            {"keyword": "k2", "search_volume": 800, "rank": 24},
            {"keyword": "k3", "search_volume": 600, "rank": 95},
        ],
        domain="whitepinedentalcare.com",
        location_code=2840,
        language_code="en",
    )
    total = int(metrics["total_search_volume"])
    appearances = int(metrics["estimated_search_appearances_monthly"])
    missed = int(metrics["missed_searches_monthly"])
    assert total > 0
    assert appearances > 0
    assert missed == max(0, total - appearances)


@pytest.mark.django_db
def test_visibility_uses_appearances_not_clicks():
    metrics = recompute_snapshot_metrics_from_keywords(
        top_keywords=[
            {"keyword": "head", "search_volume": 1000, "rank": 4},
            {"keyword": "mid", "search_volume": 1000, "rank": 24},
            {"keyword": "tail", "search_volume": 1000, "rank": 95},
        ],
        domain="whitepinedentalcare.com",
        location_code=2840,
        language_code="en",
    )
    total = int(metrics["total_search_volume"])
    clicks = int(metrics["estimated_traffic"])
    appearances = int(metrics["estimated_search_appearances_monthly"])
    visibility = int(metrics["search_visibility_percent"])
    assert total == 3000
    # Appearances should be higher than CTR clicks by definition.
    assert appearances > clicks
    # Visibility should reflect appearance coverage and be meaningfully above 0.
    assert visibility == round((appearances / total) * 100)


def test_local_mode_prefers_local_verified_rank_for_aggregates(monkeypatch):
    monkeypatch.setattr(
        "accounts.dataforseo_utils._get_competitor_average_traffic",
        lambda *args, **kwargs: 0.0,
    )
    row = {
        "keyword": "dentist near me",
        "search_volume": 1000,
        "rank": 20,
        "local_verified_rank": 2,
        "rank_source": "local_verified",
    }
    organic = recompute_snapshot_metrics_from_keywords(
        top_keywords=[row],
        domain="example.com",
        location_code=2840,
        language_code="en",
        seo_location_mode="organic",
    )
    local = recompute_snapshot_metrics_from_keywords(
        top_keywords=[row],
        domain="example.com",
        location_code=2840,
        language_code="en",
        seo_location_mode="local",
    )
    assert local["search_visibility_percent"] > organic["search_visibility_percent"]
    assert local["keywords_ranking"] == organic["keywords_ranking"] == 1
    assert local["top3_positions"] == 1
    assert organic["top3_positions"] == 0

    baseline_cmp = recompute_snapshot_metrics_from_keywords(
        top_keywords=[row],
        domain="example.com",
        location_code=2840,
        language_code="en",
        seo_location_mode="organic",
    )
    assert local_verification_affects_visibility(
        seo_location_mode="local",
        baseline_metrics=baseline_cmp,
        local_mode_metrics=local,
    )
