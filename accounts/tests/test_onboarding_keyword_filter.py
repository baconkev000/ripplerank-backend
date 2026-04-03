import json
import uuid

import pytest

from accounts.onboarding_keyword_filter import (
    apply_aeo_keyword_pipeline,
    dedupe_near_duplicate_rows,
    heuristic_filter_ranked_rows,
    openai_filter_keywords_for_aeo,
    score_keyword_for_aeo,
)


def test_score_service_and_location():
    seeds = [{"tokens": ["whitening", "teeth"]}]
    st = {"whitening", "teeth"}
    assert (
        score_keyword_for_aeo(
            "teeth whitening salt lake",
            seed_tokens=st,
            location_tokens={"salt", "lake"},
            brand_tokens=set(),
        )
        >= 3
    )


def test_score_generic_penalty_drops_toastpaste():
    st = {"cleaning"}
    s = score_keyword_for_aeo(
        "best toothpaste brands",
        seed_tokens=st,
        location_tokens=set(),
        brand_tokens=set(),
    )
    assert s < 3


def test_dedupe_keeps_higher_volume():
    rows = [
        {"keyword": "emergency dentist near me", "search_volume": 100, "rank": 5},
        {"keyword": "emergency dentist near me", "search_volume": 50, "rank": 3},
    ]
    out = dedupe_near_duplicate_rows(rows)
    assert len(out) == 1
    assert out[0]["search_volume"] == 100


def test_dedupe_wisdom_teeth_plural_variants():
    rows = [
        {"keyword": "wisdom teeth removal salt lake city utah", "search_volume": 100, "rank": 1},
        {"keyword": "wisdom tooth removal salt lake city", "search_volume": 80, "rank": 2},
    ]
    out = dedupe_near_duplicate_rows(rows)
    assert len(out) == 1
    assert out[0]["search_volume"] == 100


def test_heuristic_filter_keeps_strong_intent():
    rows = [
        {"keyword": "cheap veneers cost", "search_volume": 200, "rank": 4},
        {"keyword": "toothpaste ingredients", "search_volume": 9000, "rank": 1},
    ]
    seeds = [{"tokens": ["veneers", "cosmetic"]}]
    ctx = {"location": "Utah", "business_name": "Smile Co"}
    out = heuristic_filter_ranked_rows(rows, context=ctx, seeds=seeds)
    kws = {r["keyword"] for r in out}
    assert "cheap veneers cost" in kws
    assert "toothpaste ingredients" not in kws
    assert all(r.get("aeo_score", 0) >= 3 for r in out)


def test_apply_pipeline_falls_back_when_openai_fails(monkeypatch):
    rows = [
        {"keyword": "best dentist reviews", "search_volume": 100, "rank": 2},
    ]
    seeds = [{"tokens": ["dentist"]}]
    ctx = {"location": "Austin, TX", "business_name": "Acme Dental"}

    monkeypatch.setattr(
        "accounts.onboarding_keyword_filter.openai_filter_keywords_for_aeo",
        lambda *a, **k: ([], "no api"),
    )

    def _fake_enrich(current, *, context, need, **kwargs):
        extras = [
            {
                "keyword": f"austin dental topic {uuid.uuid4()}",
                "category": "service",
                "reason": "test fill",
            }
            for _ in range(need)
        ]
        return extras, None

    monkeypatch.setattr(
        "accounts.onboarding_keyword_filter.openai_enrich_keywords_for_minimum",
        _fake_enrich,
    )

    out = apply_aeo_keyword_pipeline(rows, context=ctx, seeds=seeds)
    assert len(out) >= 10
    assert any(r.get("keyword") == "best dentist reviews" for r in out)


def test_openai_filter_parses_json_array(monkeypatch):
    class FakeChoice:
        def __init__(self, content: str):
            self.message = type("M", (), {"content": content})()

    class FakeCompletion:
        def __init__(self, content: str):
            self.choices = [FakeChoice(content)]

    def fake_create(**kwargs):
        payload = [
            {"keyword": "best dentist reviews", "category": "trust", "reason": "comparison intent"},
        ]
        return FakeCompletion(json.dumps(payload))

    monkeypatch.setattr(
        "accounts.openai_utils._get_client",
        lambda *a, **k: type("C", (), {"chat": type("ch", (), {"completions": type("co", (), {"create": staticmethod(fake_create)})()})()})(),
    )
    monkeypatch.setattr("accounts.openai_utils._get_model", lambda: "gpt-4o-mini")

    out, err = openai_filter_keywords_for_aeo(["best dentist reviews"])
    assert err is None
    assert len(out) == 1
    assert out[0]["category"] == "trust"
