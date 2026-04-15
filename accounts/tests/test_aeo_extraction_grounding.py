"""Tests for Phase 3 AEO extraction: brand_mentioned from URL/domain matching only (code, not LLM)."""

from accounts.aeo.aeo_extraction_utils import (
    merge_citations_rankings_across_platform_cells,
    merged_target_url_position,
    unique_business_count_excluding_target,
    _domain_grounds_brand,
    _sanitize_competitors,
    brand_effectively_cited,
    citations_ranking_for_prompt_coverage,
    normalize_extraction_payload,
    parse_competitor_raw_item,
    programmatic_tracked_brand_from_urls,
    tracked_domain_listed_in_competitors,
)


def _base_payload(**overrides):
    base = {
        "competitors": [],
        "ranking_order": [],
        "citations": [],
        "sentiment": "neutral",
        "confidence_score": 0.9,
    }
    base.update(overrides)
    return base


def test_competitors_only_no_target_name_brand_false():
    raw = (
        "Here are some options: Murray Dental, Summit Smiles, and River City Family Dentistry "
        "are well regarded in the area."
    )
    out = normalize_extraction_payload(
        _base_payload(
            competitors=["Murray Dental", "Summit Smiles"],
        ),
        raw_response=raw,
        tracked_business_name="White Pine Dental",
        tracked_website_domain="whitepinedental.com",
    )
    assert out["brand_mentioned"] is False
    assert out["mention_position"] == "none"
    assert out["mention_count"] == 0
    assert any(c.get("name") == "Murray Dental" for c in out["competitors"])


def test_name_in_raw_without_url_does_not_ground_even_when_domain_configured():
    raw = "Patients often recommend White Pine Dental for routine cleanings and cosmetic work."
    out = normalize_extraction_payload(
        _base_payload(),
        raw_response=raw,
        tracked_business_name="White Pine Dental",
        tracked_website_domain="whitepinedental.com",
    )
    assert out["brand_mentioned"] is False
    assert out["mention_count"] == 0
    assert out["mention_position"] == "none"


def test_no_tracked_domain_cannot_ground_from_urls():
    raw = "See https://whitepinedental.com for appointments."
    out = normalize_extraction_payload(
        _base_payload(),
        raw_response=raw,
        tracked_business_name="White Pine Dental",
        tracked_website_domain="",
    )
    assert out["brand_mentioned"] is False


def test_model_payload_ignored_for_brand_without_url_evidence():
    raw = "Only Murray Dental and generic dental offices are mentioned here."
    out = normalize_extraction_payload(
        _base_payload(),
        raw_response=raw,
        tracked_business_name="White Pine Dental",
        tracked_website_domain="whitepinedental.com",
    )
    assert out["brand_mentioned"] is False
    assert out["mention_position"] == "none"
    assert out["mention_count"] == 0


def test_invariant_no_tracked_domain_yields_no_brand():
    out = normalize_extraction_payload(
        _base_payload(),
        raw_response="Some answer text without business context.",
        tracked_business_name="",
        tracked_website_domain="",
    )
    assert out["brand_mentioned"] is False
    assert out["mention_position"] == "none"
    assert out["mention_count"] == 0


def test_sanitize_competitors_dedupes_same_root_url():
    raw = [
        {"name": "Acme Dental", "url": "https://acme.com/about"},
        {"name": "Acme Dentistry", "url": "https://www.acme.com/team"},
        {"name": "Beta Clinic", "url": "https://beta.org"},
    ]
    out = _sanitize_competitors(raw)
    assert len(out) == 2
    assert out[0]["name"] == "Acme Dental"
    assert out[1]["name"] == "Beta Clinic"


def test_parse_competitor_python_repr_string():
    """DB may store dicts as Python repr strings instead of JSON objects."""
    s = "{'name': 'Cottonwood Dental', 'url': 'https://www.cottonwooddental.com'}"
    out = parse_competitor_raw_item(s)
    assert out["name"] == "Cottonwood Dental"
    assert out["url"] == "https://www.cottonwooddental.com"


def test_sanitize_competitors_repr_strings_become_json_shapes():
    raw = [
        "{'name': 'Murray Dental', 'url': 'https://www.murraydental.com'}",
        '{"name": "Beta", "url": "https://beta.example.com"}',
    ]
    out = _sanitize_competitors(raw)
    assert len(out) == 2
    assert out[0] == {"name": "Murray Dental", "url": "https://www.murraydental.com"}
    assert out[1]["name"] == "Beta"


def test_sanitize_competitors_legacy_strings():
    out = _sanitize_competitors(["Foo", "Bar", "Foo"])
    assert len(out) == 2
    assert out[0] == {"name": "Foo", "url": ""}
    assert out[1]["name"] == "Bar"


def test_domain_only_grounds_brand():
    raw = "Book online at https://whitepinedental.com/appointments"
    out = normalize_extraction_payload(
        _base_payload(),
        raw_response=raw,
        tracked_business_name="White Pine Dental",
        tracked_website_domain="whitepinedental.com",
    )
    assert out["brand_mentioned"] is True
    assert out["mention_count"] >= 1


def test_domain_prefix_collision_does_not_ground_saltlakedental_vs_care():
    """First label saltlakedental must not match inside saltlakedentalcare.com."""
    raw = "Visit Salt Lake Dental Care at https://saltlakedentalcare.com for more info."
    assert _domain_grounds_brand(raw, "saltlakedental.com") is False
    out = normalize_extraction_payload(
        _base_payload(),
        raw_response=raw,
        tracked_business_name="Zyzzyva Dental Unique Tracked Name",
        tracked_website_domain="saltlakedental.com",
    )
    assert out["brand_mentioned"] is False
    assert out["mention_count"] == 0


def test_domain_grounds_exact_tracked_host_in_text():
    assert _domain_grounds_brand("See https://saltlakedental.com today.", "saltlakedental.com") is True


def test_domain_grounds_www_variant():
    assert _domain_grounds_brand("Visit www.saltlakedental.com for hours.", "saltlakedental.com") is True


def test_domain_grounds_subdomain_of_tracked():
    assert _domain_grounds_brand("Book at https://portal.saltlakedental.com/x", "saltlakedental.com") is True


def test_competitors_exact_tracked_domain_still_grounds_when_raw_has_only_prefix_collision():
    """tracked_domain_listed_in_competitors remains authoritative when raw text cites a different root."""
    comps = [{"name": "Our Office", "url": "https://saltlakedental.com/"}]
    raw = "Another option is https://saltlakedentalcare.com only."
    out = normalize_extraction_payload(
        _base_payload(competitors=comps),
        raw_response=raw,
        tracked_business_name="Not Mentioned In Prose",
        tracked_website_domain="saltlakedental.com",
    )
    assert out["brand_mentioned"] is True
    assert out["mention_count"] >= 1


def test_target_url_in_competitors_list_grounds_brand_when_raw_text_misses_name():
    """LLMs often list the business only under competitors with URL; raw prose may not repeat the name."""
    comps = [
        {"url": "https://www.saltlakedentalcare.com/", "name": "Salt Lake Dental Care"},
        {"url": "https://roseman.dental/", "name": "Roseman Dental"},
    ]
    raw = "Here are several dental practices that commonly appear in local search-style answers."
    out = normalize_extraction_payload(
        _base_payload(competitors=comps),
        raw_response=raw,
        tracked_business_name="Salt Lake Dental Care",
        tracked_website_domain="saltlakedentalcare.com",
    )
    assert out["brand_mentioned"] is True
    assert out["mention_count"] >= 1


def test_tracked_domain_listed_in_competitors_detects_sample_json():
    sample = [
        {"url": "https://www.saltlakedentalcare.com/", "name": "Salt Lake Dental Care"},
        {"url": "https://roseman.dental/", "name": "Roseman Dental"},
    ]
    assert tracked_domain_listed_in_competitors("saltlakedentalcare.com", sample) is True
    assert brand_effectively_cited(False, sample, tracked_website_url_or_domain="https://www.saltlakedentalcare.com/") is True


def test_brand_effectively_cited_respects_stored_flag():
    assert brand_effectively_cited(True, [], tracked_website_url_or_domain="") is True


def test_citations_ranking_order_and_target_position():
    cites = ["other.com", "https://www.example.com/x", "not-a-valid-host"]
    comps = [
        {"name": "Other Co", "url": "https://other.com"},
        {"name": "Wrong Name", "url": "https://example.com"},
    ]
    rows, pos = citations_ranking_for_prompt_coverage(
        cites,
        comps,
        tracked_website_url_or_domain="example.com",
        brand_mentioned=True,
        tracked_business_name="My Dental",
    )
    assert pos == 2
    assert len(rows) == 2  # invalid host fragment → skipped
    assert rows[0]["name"] == "Other Co" and rows[0]["is_target"] is False
    assert rows[0]["url"] == "https://other.com"
    assert rows[1]["name"] == "My Dental" and rows[1]["is_target"] is True
    assert rows[1]["url"] == "https://www.example.com/x"


def test_citations_ranking_marks_target_by_domain_even_when_brand_flag_false():
    rows, pos = citations_ranking_for_prompt_coverage(
        ["https://example.com"],
        [{"name": "Listed As", "url": "https://example.com"}],
        tracked_website_url_or_domain="example.com",
        brand_mentioned=False,
        tracked_business_name="Real Brand Name",
    )
    assert pos == 1
    assert rows[0]["name"] == "Real Brand Name"
    assert rows[0]["is_target"] is True
    assert rows[0]["url"] == "https://example.com"


def test_merge_citations_rankings_unions_platforms_and_renumbers():
    openai_cell = {
        "has_data": True,
        "citations_ranking": [
            {"name": "Alpha Co", "position": 1, "is_target": False, "url": "https://alpha.example"},
            {"name": "My Brand", "position": 2, "is_target": True, "url": "https://mine.example"},
        ],
    }
    gemini_cell = {
        "has_data": True,
        "citations_ranking": [
            {"name": "Gamma Inc", "position": 1, "is_target": False, "url": "https://gamma.example"},
            {"name": "My Brand", "position": 4, "is_target": True, "url": "https://mine.example/longer"},
        ],
    }
    merged = merge_citations_rankings_across_platform_cells([openai_cell, gemini_cell])
    names = [r["name"] for r in merged]
    assert "Alpha Co" in names
    assert "Gamma Inc" in names
    assert "My Brand" in names
    assert len(merged) == 3
    # Best position for My Brand is min(2, 4) → sorts after 1,1 (Alpha, Gamma) → third row
    my_row = next(r for r in merged if r["name"] == "My Brand")
    assert my_row["position"] == 3
    assert my_row["is_target"] is True
    assert my_row["url"] == "https://mine.example/longer"
    assert merged_target_url_position(merged) == 3


def test_merge_citations_rankings_skips_empty_and_no_data_cells():
    assert merge_citations_rankings_across_platform_cells([]) == []
    assert (
        merge_citations_rankings_across_platform_cells(
            [{"has_data": False, "citations_ranking": [{"name": "X", "position": 1, "is_target": False}]}]
        )
        == []
    )


def test_unique_business_count_excluding_target():
    assert unique_business_count_excluding_target([]) == 0
    assert (
        unique_business_count_excluding_target(
            [
                {"name": "A", "position": 1, "is_target": False},
                {"name": "B", "position": 2, "is_target": True},
            ]
        )
        == 1
    )
    assert (
        unique_business_count_excluding_target(
            [
                {"name": "A", "position": 1, "is_target": False},
                {"name": "B", "position": 2, "is_target": False},
            ]
        )
        == 2
    )


def test_programmatic_tracked_brand_from_urls_unions_raw_and_competitors():
    comps = [{"name": "Other", "url": "https://other.example.com/"}]
    brand, count = programmatic_tracked_brand_from_urls(
        "tracked.com",
        "Plain text only.",
        comps,
    )
    assert brand is False
    brand2, count2 = programmatic_tracked_brand_from_urls(
        "tracked.com",
        "Visit https://www.tracked.com today.",
        comps,
    )
    assert brand2 is True
    assert count2 >= 1
