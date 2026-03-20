import pytest

from accounts.dataforseo_utils import recompute_snapshot_metrics_from_keywords


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
