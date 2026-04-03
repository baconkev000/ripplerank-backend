import pytest

from accounts.onboarding_onpage import extract_onboarding_page_record


def test_extract_onboarding_page_record_minimal():
    page = {
        "url": "https://example.com/pricing/",
        "meta": {
            "title": "Pricing — Example",
            "description": "Plans and pricing",
            "keywords": "saas, pricing, b2b",
        },
        "content": {
            "headings": [
                {"tag": "h1", "text": "Our pricing"},
                {"tag": "h2", "text": "Starter plan"},
                {"tag": "h3", "text": "FAQ"},
            ],
        },
    }
    out = extract_onboarding_page_record(
        page,
        {"business_name": "Example", "location": "Austin, TX"},
    )
    assert out["url_path"] == "/pricing/"
    assert out["page_title"] == "Pricing — Example"
    assert out["meta_description"] == "Plans and pricing"
    assert out["h1"] == "Our pricing"
    assert any("H2:" in x for x in out["h2_h3_headings"])
    assert "saas" in [x.lower() for x in out["primary_keyword_candidates"]]
