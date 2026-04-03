"""Pure unit tests (no DB) for onboarding prompt → topic assignment."""

from accounts.aeo.aeo_utils import (
    assign_onboarding_prompts_to_selected_topics,
    aeo_business_input_from_onboarding_payload,
)


def test_assign_distributes_across_topics():
    combined = [{"prompt": f"prompt-{i}"} for i in range(10)]
    topics = ["t1", "t2", "t3"]
    out = assign_onboarding_prompts_to_selected_topics(combined, topics)
    assert sum(len(v) for v in out.values()) == 10
    assert out["t1"][0] == "prompt-0"
    assert out["t2"][0] == "prompt-1"
    assert out["t3"][0] == "prompt-2"
    assert out["t1"][-1] == "prompt-9"


def test_onboarding_business_input_uses_topics_not_profile():
    bi = aeo_business_input_from_onboarding_payload(
        business_name="Acme",
        website_url="https://acme.com",
        location="Austin, TX",
        language="English",
        selected_topics=["dental implants", "teeth whitening"],
    )
    d = bi.as_dict()
    assert "implant" in d["industry"].lower() or "dental" in d["industry"].lower()
    assert len(d["services"]) == 2
    assert d["language"] == "English"
