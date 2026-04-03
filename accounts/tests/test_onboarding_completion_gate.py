"""Onboarding completion requires keywords, AEO responses, and extractions."""

import pytest
from django.contrib.auth import get_user_model

from accounts.models import (
    AEOExtractionSnapshot,
    AEOResponseSnapshot,
    BusinessProfile,
    OnboardingOnPageCrawl,
)
from accounts.onboarding_completion import business_profile_fully_onboarded
from accounts.serializers import _aeo_prompt_target_count

User = get_user_model()


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
    AEOResponseSnapshot.objects.create(
        profile=profile,
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
    )
    OnboardingOnPageCrawl.objects.create(
        user=user,
        business_profile=profile,
        domain="example.com",
        status=OnboardingOnPageCrawl.STATUS_COMPLETED,
        ranked_keywords=[{"keyword": "widgets", "search_volume": 100, "rank": 3}],
    )
    rsp = AEOResponseSnapshot.objects.create(
        profile=profile,
        prompt_text="q",
        prompt_hash="cafebabe",
        platform="openai",
    )
    AEOExtractionSnapshot.objects.create(response_snapshot=rsp)
    assert business_profile_fully_onboarded(profile) is True
