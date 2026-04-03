"""Unit tests for onboarding competitor visibility (AEO extractions)."""

from types import SimpleNamespace

import pytest

from accounts.aeo.aeo_scoring_utils import (
    _pick_three_onboarding_competitor_rows,
    aeo_onboarding_competitors_visibility,
)


def test_pick_three_target_first():
    full = [
        {"appearances": 10, "brand": "T", "is_target": True},
        {"appearances": 5, "brand": "A", "is_target": False},
        {"appearances": 3, "brand": "B", "is_target": False},
        {"appearances": 1, "brand": "C", "is_target": False},
    ]
    out = _pick_three_onboarding_competitor_rows(full, 0)
    assert [r["brand"] for r in out] == ["T", "A", "B"]


def test_pick_three_target_second():
    full = [
        {"appearances": 10, "brand": "A", "is_target": False},
        {"appearances": 8, "brand": "T", "is_target": True},
        {"appearances": 3, "brand": "B", "is_target": False},
    ]
    out = _pick_three_onboarding_competitor_rows(full, 1)
    assert [r["brand"] for r in out] == ["A", "T", "B"]


def test_pick_three_target_eighth():
    letters = [chr(65 + i) for i in range(8)]
    full = [{"appearances": 20 - i, "brand": letters[i], "is_target": (i == 7)} for i in range(8)]
    target_idx = 7
    out = _pick_three_onboarding_competitor_rows(full, target_idx)
    assert len(out) == 3
    assert out[0]["brand"] == "A"
    assert out[1]["brand"] == "B"
    assert out[2]["brand"] == "H"
    assert out[2]["is_target"] is True


def test_aeo_onboarding_competitors_visibility_counts(monkeypatch):
    profile = SimpleNamespace(
        business_name="My Brand",
        website_url="https://mybrand.example",
    )

    extractions = [
        SimpleNamespace(
            brand_mentioned=True,
            competitors_json=[{"name": "Alpha Co", "url": "https://alpha.example"}],
            sentiment="positive",
        ),
        SimpleNamespace(
            brand_mentioned=False,
            competitors_json=[{"name": "Alpha Co", "url": ""}, {"name": "Beta LLC", "url": ""}],
            sentiment="neutral",
        ),
        SimpleNamespace(
            brand_mentioned=False,
            competitors_json=[{"name": "Beta LLC", "url": ""}],
            sentiment="neutral",
        ),
        SimpleNamespace(
            brand_mentioned=True,
            competitors_json=[],
            sentiment="positive",
        ),
    ]

    slots = [(None, ex) for ex in extractions]
    monkeypatch.setattr(
        "accounts.aeo.aeo_scoring_utils._aeo_onboarding_response_extractions",
        lambda _p: slots,
    )

    out = aeo_onboarding_competitors_visibility(profile)
    assert out["has_data"] is True
    assert out["total_prompts"] == 4
    # Alpha: 2 list rows, Beta: 2, target: 2 units -> 50%, 50%, 50% — sort by name tie-break
    assert len(out["rows"]) == 3
    brands = {r["brand"] for r in out["rows"]}
    assert brands == {"Alpha Co", "Beta LLC", "My Brand"}
    for r in out["rows"]:
        assert r["visibility_pct"] == 50.0
    target_row = next(r for r in out["rows"] if r["is_target"])
    assert target_row["sentiment"] == "positive"


def test_aeo_onboarding_competitors_visibility_counts_slots_without_extraction(monkeypatch):
    """Denominator includes LLM runs that have no extraction yet (numerator unchanged)."""
    profile = SimpleNamespace(
        business_name="My Brand",
        website_url="https://mybrand.example",
    )

    extractions = [
        SimpleNamespace(
            brand_mentioned=True,
            competitors_json=[{"name": "Alpha Co", "url": "https://alpha.example"}],
            sentiment="positive",
        ),
    ]
    slots = [(None, extractions[0]), (None, None)]

    monkeypatch.setattr(
        "accounts.aeo.aeo_scoring_utils._aeo_onboarding_response_extractions",
        lambda _p: slots,
    )

    out = aeo_onboarding_competitors_visibility(profile)
    assert out["total_prompts"] == 2
    assert next(r for r in out["rows"] if r["is_target"])["visibility_pct"] == 50.0
    assert next(r for r in out["rows"] if r["brand"] == "Alpha Co")["visibility_pct"] == 50.0


def test_aeo_onboarding_competitors_visibility_duplicate_rows_same_answer(monkeypatch):
    """Two competitor list entries for the same brand in one response count as two cites."""
    profile = SimpleNamespace(
        business_name="My Brand",
        website_url="https://mybrand.example",
    )

    extractions = [
        SimpleNamespace(
            brand_mentioned=False,
            competitors_json=[
                {"name": "Alpha Co", "url": ""},
                {"name": "Alpha Co", "url": ""},
            ],
            sentiment="neutral",
        ),
        SimpleNamespace(
            brand_mentioned=False,
            competitors_json=[{"name": "Beta LLC", "url": ""}],
            sentiment="neutral",
        ),
    ]
    slots = [(None, ex) for ex in extractions]

    monkeypatch.setattr(
        "accounts.aeo.aeo_scoring_utils._aeo_onboarding_response_extractions",
        lambda _p: slots,
    )

    out = aeo_onboarding_competitors_visibility(profile)
    assert out["total_prompts"] == 2
    alpha = next(r for r in out["rows"] if r["brand"] == "Alpha Co")
    beta = next(r for r in out["rows"] if r["brand"] == "Beta LLC")
    assert alpha["visibility_pct"] == 100.0
    assert beta["visibility_pct"] == 50.0
