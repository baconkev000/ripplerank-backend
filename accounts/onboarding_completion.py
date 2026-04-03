"""
Decide if a user has finished onboarding (profile + keywords + AEO prompts + AEO scan pipeline).

Used by auth/status, post-login redirects, and should stay aligned with onboarding hydration.
"""
from __future__ import annotations

from .dataforseo_utils import normalize_domain
from .models import (
    AEOExtractionSnapshot,
    AEOResponseSnapshot,
    BusinessProfile,
    OnboardingOnPageCrawl,
    SEOOverviewSnapshot,
)
from .serializers import _aeo_prompt_target_count


def profile_has_ranked_keywords(profile: BusinessProfile) -> bool:
    """
    True if we have a non-empty keyword list from onboarding Labs crawl or SEO snapshot cache.
    """
    domain = normalize_domain(profile.website_url or "")
    if domain:
        crawl = (
            OnboardingOnPageCrawl.objects.filter(
                user=profile.user,
                domain=domain,
                status=OnboardingOnPageCrawl.STATUS_COMPLETED,
            )
            .order_by("-created_at")
            .first()
        )
        if crawl is not None:
            rk = crawl.ranked_keywords
            if isinstance(rk, list) and len(rk) > 0:
                return True
    snap = (
        SEOOverviewSnapshot.objects.filter(user=profile.user)
        .order_by("-last_fetched_at", "-id")
        .only("top_keywords")
        .first()
    )
    if snap is not None:
        tk = getattr(snap, "top_keywords", None) or []
        if isinstance(tk, list) and len(tk) > 0:
            return True
    return False


def profile_has_aeo_response_snapshots(profile: BusinessProfile) -> bool:
    return AEOResponseSnapshot.objects.filter(profile=profile).exists()


def profile_has_aeo_extraction_snapshots(profile: BusinessProfile) -> bool:
    return AEOExtractionSnapshot.objects.filter(response_snapshot__profile=profile).exists()


def business_profile_fully_onboarded(profile: BusinessProfile | None) -> bool:
    if profile is None:
        return False
    if not (
        (profile.business_name or "").strip()
        and (profile.website_url or "").strip()
        and (profile.business_address or "").strip()
    ):
        return False

    target = _aeo_prompt_target_count()
    prompts = profile.selected_aeo_prompts or []
    prompts = [str(x).strip() for x in prompts if str(x).strip()]
    if len(prompts) != target:
        return False

    domain = normalize_domain(profile.website_url or "")
    if not domain:
        return False

    if not profile_has_ranked_keywords(profile):
        return False

    if not profile_has_aeo_response_snapshots(profile):
        return False

    if not profile_has_aeo_extraction_snapshots(profile):
        return False

    return True


def user_has_completed_full_onboarding(user) -> bool:
    if user is None or not user.is_authenticated:
        return False
    qs = BusinessProfile.objects.filter(user=user)
    profile = qs.filter(is_main=True).first() or qs.first()
    return business_profile_fully_onboarded(profile)
