import json

from accounts.onboarding_review_topics import (
    dedupe_and_cap_topics,
    parse_review_topics_json,
)


def test_parse_review_topics_json_valid():
    payload = {
        "topics": [
            {"topic": "Corporate Cards", "category": "product", "rationale": "Core SKU"},
            {"topic": "Expense Reporting", "category": "service"},
        ]
    }
    items, err = parse_review_topics_json(json.dumps(payload))
    assert err is None
    assert len(items) == 2
    assert items[0]["topic"] == "Corporate Cards"
    assert items[0]["category"] == "product"
    assert items[0]["rationale"] == "Core SKU"


def test_parse_review_topics_json_invalid_returns_error():
    items, err = parse_review_topics_json("not json")
    assert items == []
    assert err and "review_topics_invalid_json" in err


def test_dedupe_and_cap_topics():
    raw = [
        {"topic": "Same Topic"},
        {"topic": "same topic", "category": "x"},
        {"topic": "Other"},
    ]
    out = dedupe_and_cap_topics(raw, cap=20)
    assert len(out) == 2
    assert out[0]["topic"] == "Same Topic"
    assert out[1]["topic"] == "Other"


def test_dedupe_and_cap_topics_respects_max():
    raw = [{"topic": f"T{i}"} for i in range(25)]
    out = dedupe_and_cap_topics(raw, cap=20)
    assert len(out) == 20
