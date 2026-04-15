"""Onboarding completion requires keywords, AEO responses, and extractions."""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import (
    AEOPromptExecutionAggregate,
    AEOExecutionRun,
    AEOExtractionSnapshot,
    AEOResponseSnapshot,
    BusinessProfile,
    OnboardingOnPageCrawl,
)
from accounts.onboarding_completion import (
    business_profile_fully_onboarded,
    effective_dashboard_plan_slug_for_owned_business_profiles,
    user_has_completed_full_onboarding,
)
from accounts.serializers import _aeo_prompt_target_count

User = get_user_model()


@pytest.mark.django_db
def test_effective_plan_slug_advanced_includes_enterprise_alias():
    user = User.objects.create_user(username="plan1", email="plan1@example.com", password="x")
    BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Co",
        website_url="https://co.example",
        plan="enterprise",
        stripe_subscription_status="active",
    )
    assert effective_dashboard_plan_slug_for_owned_business_profiles(user) == "advanced"


@pytest.mark.django_db
def test_not_complete_without_aeo_pipeline():
    user = User.objects.create_user(username="og1@example.com", email="og1@example.com", password="x")
    n = _aeo_prompt_target_count()
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Acme",
        website_url="https://example.com",
        business_address="US",
        selected_aeo_prompts=[f"prompt-{i}" for i in range(n)],
    )
    OnboardingOnPageCrawl.objects.create(
        user=user,
        business_profile=profile,
        domain="example.com",
        status=OnboardingOnPageCrawl.STATUS_COMPLETED,
        ranked_keywords=[{"keyword": "widgets", "search_volume": 100, "rank": 3}],
    )
    assert business_profile_fully_onboarded(profile) is False


@pytest.mark.django_db
def test_not_complete_with_responses_only():
    user = User.objects.create_user(username="og2@example.com", email="og2@example.com", password="x")
    n = _aeo_prompt_target_count()
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Acme",
        website_url="https://example.com",
        business_address="US",
        selected_aeo_prompts=[f"prompt-{i}" for i in range(n)],
    )
    OnboardingOnPageCrawl.objects.create(
        user=user,
        business_profile=profile,
        domain="example.com",
        status=OnboardingOnPageCrawl.STATUS_COMPLETED,
        ranked_keywords=[{"keyword": "widgets", "search_volume": 100, "rank": 3}],
    )
    run = AEOExecutionRun.objects.create(
        profile=profile,
        status=AEOExecutionRun.STATUS_COMPLETED,
        prompt_count_executed=1,
    )
    AEOResponseSnapshot.objects.create(
        profile=profile,
        execution_run=run,
        prompt_text="q",
        prompt_hash="deadbeef",
        platform="openai",
    )
    assert business_profile_fully_onboarded(profile) is False


@pytest.mark.django_db
def test_complete_with_extractions():
    user = User.objects.create_user(username="og3@example.com", email="og3@example.com", password="x")
    n = _aeo_prompt_target_count()
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Acme",
        website_url="https://example.com",
        business_address="US",
        selected_aeo_prompts=[f"prompt-{i}" for i in range(n)],
        stripe_subscription_id="sub_onb_test",
        stripe_subscription_status="active",
    )
    OnboardingOnPageCrawl.objects.create(
        user=user,
        business_profile=profile,
        domain="example.com",
        status=OnboardingOnPageCrawl.STATUS_COMPLETED,
        ranked_keywords=[{"keyword": "widgets", "search_volume": 100, "rank": 3}],
    )
    run = AEOExecutionRun.objects.create(
        profile=profile,
        status=AEOExecutionRun.STATUS_COMPLETED,
        prompt_count_executed=1,
    )
    rsp = AEOResponseSnapshot.objects.create(
        profile=profile,
        execution_run=run,
        prompt_text="q",
        prompt_hash="cafebabe",
        platform="openai",
    )
    AEOExtractionSnapshot.objects.create(response_snapshot=rsp)
    profile.refresh_from_db()
    assert business_profile_fully_onboarded(profile) is True


@pytest.mark.django_db
def test_not_complete_with_aggregate_only_and_missing_run_artifacts():
    user = User.objects.create_user(username="og4@example.com", email="og4@example.com", password="x")
    n = _aeo_prompt_target_count()
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Acme",
        website_url="https://example.com",
        business_address="US",
        selected_aeo_prompts=[f"prompt-{i}" for i in range(n)],
    )
    run = AEOExecutionRun.objects.create(
        profile=profile,
        status=AEOExecutionRun.STATUS_COMPLETED,
        prompt_count_executed=1,
    )
    OnboardingOnPageCrawl.objects.create(
        user=user,
        business_profile=profile,
        domain="example.com",
        status=OnboardingOnPageCrawl.STATUS_COMPLETED,
        ranked_keywords=[{"keyword": "widgets", "search_volume": 100, "rank": 3}],
    )
    AEOPromptExecutionAggregate.objects.create(
        profile=profile,
        execution_run=run,
        prompt_hash="agg-only",
        prompt_text="q",
    )
    assert business_profile_fully_onboarded(profile) is False


@pytest.mark.django_db
def test_user_onboarding_complete_when_sibling_owned_profile_is_complete():
    """Main can be a new/incomplete profile while another owned profile is fully onboarded."""
    user = User.objects.create_user(username="og5@example.com", email="og5@example.com", password="x")
    n = _aeo_prompt_target_count()
    prompts = [f"prompt-{i}" for i in range(n)]

    complete_profile = BusinessProfile.objects.create(
        user=user,
        is_main=False,
        business_name="Acme",
        website_url="https://example.com",
        business_address="US",
        selected_aeo_prompts=prompts,
        stripe_subscription_id="sub_onb_test",
        stripe_subscription_status="active",
    )
    OnboardingOnPageCrawl.objects.create(
        user=user,
        business_profile=complete_profile,
        domain="example.com",
        status=OnboardingOnPageCrawl.STATUS_COMPLETED,
        ranked_keywords=[{"keyword": "widgets", "search_volume": 100, "rank": 3}],
    )
    run = AEOExecutionRun.objects.create(
        profile=complete_profile,
        status=AEOExecutionRun.STATUS_COMPLETED,
        prompt_count_executed=1,
    )
    rsp = AEOResponseSnapshot.objects.create(
        profile=complete_profile,
        execution_run=run,
        prompt_text="q",
        prompt_hash="cafebabe",
        platform="openai",
    )
    AEOExtractionSnapshot.objects.create(response_snapshot=rsp)
    complete_profile.refresh_from_db()
    assert business_profile_fully_onboarded(complete_profile) is True

    new_main = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Beta",
        website_url="https://beta.example",
        business_address="US",
        selected_aeo_prompts=[],
        stripe_subscription_id="sub_onb_test",
        stripe_subscription_status="active",
    )
    assert business_profile_fully_onboarded(new_main) is False
    assert user_has_completed_full_onboarding(user) is True
