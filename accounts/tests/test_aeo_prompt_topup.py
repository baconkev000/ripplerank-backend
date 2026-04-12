"""Top-up rounds in build_full_aeo_prompt_plan after the four-type pass."""

import pytest

from accounts.aeo.aeo_utils import aeo_business_input_from_profile, build_full_aeo_prompt_plan
from accounts.models import BusinessProfile


@pytest.mark.django_db
def test_topup_reaches_target_when_model_adds_prompts(monkeypatch, settings, django_user_model):
    settings.AEO_PROMPT_TOPUP_MAX_ROUNDS = 5
    settings.AEO_PROMPT_TOPUP_BUFFER = 8
    settings.AEO_ONBOARDING_OPENAI_MAX_BATCH_SIZE = 24

    call_i = {"n": 0}

    def fake_run(ctx, seed_prompts=None, *, max_additional=12, **kwargs):
        i = call_i["n"]
        call_i["n"] += 1
        if i < 4:
            return [{"prompt": f"seed{i}", "weight": 1.0}]
        return [{"prompt": "fillA", "weight": 1.0}, {"prompt": "fillB", "weight": 1.0}]

    monkeypatch.setattr("accounts.aeo.aeo_utils.run_prompt_batch_via_openai", fake_run)

    user = django_user_model.objects.create_user(username="tu1", password="pw")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Biz",
        website_url="https://biz.example",
    )
    ctx = aeo_business_input_from_profile(profile)
    plan = build_full_aeo_prompt_plan(profile, business_input=ctx, target_combined_count=6)
    combined = plan["combined"]
    meta = plan["meta"]

    assert len(combined) == 6
    assert meta["openai_status"] == "ok"
    assert meta["combined_shortfall"] == 0


@pytest.mark.django_db
def test_topup_stops_when_no_new_prompts_after_dedupe(monkeypatch, settings, django_user_model):
    settings.AEO_PROMPT_TOPUP_MAX_ROUNDS = 5
    settings.AEO_PROMPT_TOPUP_BUFFER = 8

    call_i = {"n": 0}

    def fake_run(ctx, seed_prompts=None, *, max_additional=12, **kwargs):
        i = call_i["n"]
        call_i["n"] += 1
        if i < 4:
            return [{"prompt": f"seed{i}", "weight": 1.0}]
        return [{"prompt": "seed0", "weight": 1.0}]

    monkeypatch.setattr("accounts.aeo.aeo_utils.run_prompt_batch_via_openai", fake_run)

    user = django_user_model.objects.create_user(username="tu2", password="pw")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Biz",
        website_url="https://biz.example",
    )
    ctx = aeo_business_input_from_profile(profile)
    plan = build_full_aeo_prompt_plan(profile, business_input=ctx, target_combined_count=6)
    meta = plan["meta"]

    assert len(plan["combined"]) == 4
    assert meta["openai_status"] == "partial"
    assert meta["combined_shortfall"] == 2


@pytest.mark.django_db
def test_topup_respects_max_rounds(monkeypatch, settings, django_user_model):
    settings.AEO_PROMPT_TOPUP_MAX_ROUNDS = 2
    settings.AEO_PROMPT_TOPUP_BUFFER = 8

    extras = iter(["e1", "e2", "e3", "e4", "e5"])
    call_i = {"n": 0}

    def fake_run(ctx, seed_prompts=None, *, max_additional=12, **kwargs):
        i = call_i["n"]
        call_i["n"] += 1
        if i < 4:
            return [{"prompt": f"s{i}", "weight": 1.0}]
        return [{"prompt": next(extras), "weight": 1.0}]

    monkeypatch.setattr("accounts.aeo.aeo_utils.run_prompt_batch_via_openai", fake_run)

    user = django_user_model.objects.create_user(username="tu3", password="pw")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Biz",
        website_url="https://biz.example",
    )
    ctx = aeo_business_input_from_profile(profile)
    plan = build_full_aeo_prompt_plan(profile, business_input=ctx, target_combined_count=10)
    meta = plan["meta"]

    assert len(plan["combined"]) == 6
    assert meta["openai_status"] == "partial"
    assert meta["combined_shortfall"] == 4
    assert call_i["n"] == 6


@pytest.mark.django_db
def test_topup_second_round_when_first_batch_mostly_dedupes(monkeypatch, settings, django_user_model):
    """First top-up returns many duplicates; a second round is needed to reach target."""
    settings.AEO_PROMPT_TOPUP_MAX_ROUNDS = 4
    settings.AEO_PROMPT_TOPUP_BUFFER = 8

    call_i = {"n": 0}

    def fake_run(ctx, seed_prompts=None, *, max_additional=12, **kwargs):
        i = call_i["n"]
        call_i["n"] += 1
        if i < 4:
            return [{"prompt": f"s{i}", "weight": 1.0}]
        if i == 4:
            return [
                {"prompt": "s0", "weight": 1.0},
                {"prompt": "s1", "weight": 1.0},
                {"prompt": "only_new_1", "weight": 1.0},
            ]
        return [
            {"prompt": "only_new_2", "weight": 1.0},
            {"prompt": "only_new_3", "weight": 1.0},
            {"prompt": "only_new_4", "weight": 1.0},
        ]

    monkeypatch.setattr("accounts.aeo.aeo_utils.run_prompt_batch_via_openai", fake_run)

    user = django_user_model.objects.create_user(username="tu4", password="pw")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Biz",
        website_url="https://biz.example",
    )
    ctx = aeo_business_input_from_profile(profile)
    plan = build_full_aeo_prompt_plan(profile, business_input=ctx, target_combined_count=8)

    assert len(plan["combined"]) == 8
    assert plan["meta"]["openai_status"] == "ok"
    assert call_i["n"] == 6
