"""top_keywords from DB snapshot when get_or_refresh returns empty (Keywords UI / seo profile)."""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import BusinessProfile, SEOOverviewSnapshot
from accounts.serializers import BusinessProfileSerializer

User = get_user_model()


@pytest.mark.django_db
def test_get_top_keywords_falls_back_to_stored_snapshot_when_bundle_empty(monkeypatch):
    user = User.objects.create_user(
        username="kw-fb-u", email="kw-fb@example.com", password="pw"
    )
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        website_url="https://acme.example.com",
    )
    stored = [{"keyword": "widgets", "search_volume": 900, "rank": 4}]
    SEOOverviewSnapshot.objects.create(
        user=user,
        period_start=timezone.now().date().replace(day=1),
        cached_domain="acme.example.com",
        cached_location_mode="organic",
        cached_location_code=0,
        top_keywords=stored,
    )

    monkeypatch.setattr(
        "accounts.serializers.get_or_refresh_seo_score_for_user",
        lambda user, site_url=None: {"seo_score": 0, "top_keywords": []},
    )

    ser = BusinessProfileSerializer(instance=profile)
    assert ser.data.get("top_keywords") == stored


@pytest.mark.django_db
def test_get_top_keywords_no_cross_domain_leak(monkeypatch):
    user = User.objects.create_user(
        username="kw-fb-2", email="kw-fb2@example.com", password="pw"
    )
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        website_url="https://mine.example.org",
    )
    SEOOverviewSnapshot.objects.create(
        user=user,
        period_start=timezone.now().date().replace(day=1),
        cached_domain="other-site.com",
        cached_location_mode="organic",
        cached_location_code=0,
        top_keywords=[{"keyword": "nope", "search_volume": 1, "rank": 1}],
    )

    monkeypatch.setattr(
        "accounts.serializers.get_or_refresh_seo_score_for_user",
        lambda user, site_url=None: {"seo_score": 0, "top_keywords": []},
    )

    ser = BusinessProfileSerializer(instance=profile)
    assert ser.data.get("top_keywords") == []


@pytest.mark.django_db
def test_seo_profile_api_returns_snapshot_top_keywords_when_bundle_empty(monkeypatch):
    user = User.objects.create_user(
        username="kw-api-u", email="kw-api@example.com", password="pw"
    )
    BusinessProfile.objects.create(
        user=user,
        is_main=True,
        website_url="https://shop.example.net",
    )
    stored = [{"keyword": "buy shoes", "search_volume": 1200, "rank": 8}]
    SEOOverviewSnapshot.objects.create(
        user=user,
        period_start=date(2026, 4, 1),
        cached_domain="shop.example.net",
        cached_location_mode="organic",
        cached_location_code=0,
        top_keywords=stored,
    )

    monkeypatch.setattr(
        "accounts.serializers.get_or_refresh_seo_score_for_user",
        lambda user, site_url=None: {"seo_score": 0, "top_keywords": []},
    )

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/seo/profile/")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("top_keywords") == stored


@pytest.mark.django_db
def test_skip_heavy_top_keywords_branch_unchanged(monkeypatch):
    """Onboarding path: latest snapshot by fetch time, not bundle (no fallback helper)."""
    user = User.objects.create_user(
        username="kw-skip", email="kw-skip@example.com", password="pw"
    )
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        website_url="https://a.com",
    )
    SEOOverviewSnapshot.objects.create(
        user=user,
        period_start=timezone.now().date().replace(day=1),
        cached_domain="a.com",
        top_keywords=[{"keyword": "from_snap", "search_volume": 1, "rank": 2}],
    )

    ser = BusinessProfileSerializer(
        instance=profile,
        context={"skip_heavy_profile_metrics": True},
    )
    out = ser.data.get("top_keywords") or []
    assert len(out) == 1
    assert out[0].get("keyword") == "from_snap"
