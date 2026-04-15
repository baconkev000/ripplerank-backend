"""prompt_scan_* / visibility_pending helpers and API payload (when stripe available for views import)."""

import pytest

from accounts.aeo.prompt_scan_progress import monitored_prompt_keys_in_order, prompt_scan_completed_count


class _FakeExtractionRelation:
    def __init__(self, has: bool) -> None:
        self._has = has

    def exists(self) -> bool:
        return self._has


class _FakeResp:
    def __init__(self, platform: str, has_extraction: bool) -> None:
        self.platform = platform
        self.extraction_snapshots = _FakeExtractionRelation(has_extraction)


def _latest_per_platform(rows: list) -> dict:
    best: dict[str, object] = {}
    for r in rows:
        p = str(getattr(r, "platform", "") or "").strip().lower()
        if not p or p in best:
            continue
        best[p] = r
    return best


def test_monitored_prompt_keys_dedupes_and_strips():
    assert monitored_prompt_keys_in_order(["a", " a ", "b", "", "b"]) == ["a", "b"]


def test_prompt_scan_completed_zero_until_all_three_platforms_have_extractions():
    by_prompt = {
        "only": [
            _FakeResp("openai", True),
            _FakeResp("gemini", True),
        ],
    }
    assert (
        prompt_scan_completed_count(["only"], by_prompt, _latest_per_platform) == 0
    )
    by_prompt["only"].append(_FakeResp("perplexity", True))
    assert prompt_scan_completed_count(["only"], by_prompt, _latest_per_platform) == 1


def test_prompt_scan_completed_two_prompts_partial():
    by_prompt = {
        "a": [_FakeResp("openai", True), _FakeResp("gemini", True), _FakeResp("perplexity", True)],
        "b": [_FakeResp("openai", True)],
    }
    assert prompt_scan_completed_count(["a", "b"], by_prompt, _latest_per_platform) == 1


@pytest.mark.django_db
def test_prompt_coverage_api_includes_scan_fields():
    """Full HTTP test — requires ``stripe`` because ``accounts.views`` imports it."""
    pytest.importorskip("stripe")
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    from accounts.models import AEOResponseSnapshot, AEOExtractionSnapshot, BusinessProfile

    User = get_user_model()
    user = User.objects.create_user(username="scan_api", email="scan_api@example.com", password="pw")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Biz",
        selected_aeo_prompts=["One"],
    )
    rsp = AEOResponseSnapshot.objects.create(
        profile=profile,
        prompt_text="One",
        prompt_hash="h1",
        raw_response="x",
        platform="openai",
    )
    AEOExtractionSnapshot.objects.create(response_snapshot=rsp, brand_mentioned=False)

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/aeo/prompt-coverage/")
    assert res.status_code == 200
    data = res.json()
    assert data["prompt_scan_total"] == 1
    assert data["prompt_scan_completed"] == 0
    # Only OpenAI has a snapshot and it already has an extraction — no in-flight work.
    assert data["visibility_pending"] is False
    assert data.get("recommendations_pending") is False
    assert data["prompt_fill_completed"] == 1
    assert data["prompt_fill_target"] == 10
    assert "aeo_prompt_expansion_status" in data
    assert "aeo_prompt_expansion_last_error" in data
    assert "visibility_pending_reasons" in data
    assert data["visibility_pending_reasons"]["execution_inflight"] is False
    assert "visibility_repair" in data


@pytest.mark.django_db
def test_prompt_coverage_recommendations_pending_when_phase5_in_flight(settings):
    pytest.importorskip("stripe")
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    from accounts.models import AEOExecutionRun, BusinessProfile

    settings.AEO_ENABLE_RECOMMENDATION_STAGE = True
    User = get_user_model()
    user = User.objects.create_user(username="reco_pend", email="reco_pend@example.com", password="pw")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Biz",
        selected_aeo_prompts=["One"],
    )
    AEOExecutionRun.objects.create(
        profile=profile,
        status=AEOExecutionRun.STATUS_COMPLETED,
        scoring_status=AEOExecutionRun.STAGE_COMPLETED,
        recommendation_status=AEOExecutionRun.STAGE_RUNNING,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/aeo/prompt-coverage/")
    assert res.status_code == 200
    assert res.json().get("recommendations_pending") is True


@pytest.mark.django_db
def test_prompt_coverage_cited_uses_tracked_domain_not_brand_flag():
    pytest.importorskip("stripe")
    from accounts.views import _build_aeo_prompt_coverage_payload
    from accounts.models import AEOExtractionSnapshot, AEOResponseSnapshot, BusinessProfile
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="scan_domain", email="scan_domain@example.com", password="pw")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Material Handling USA",
        website_url="https://mh-usa.com",
        selected_aeo_prompts=["Who is best for warehouse shelving?"],
    )
    rsp = AEOResponseSnapshot.objects.create(
        profile=profile,
        prompt_text="Who is best for warehouse shelving?",
        prompt_hash="h-domain",
        raw_response="x",
        platform="openai",
    )
    AEOExtractionSnapshot.objects.create(
        response_snapshot=rsp,
        # Simulate legacy/misaligned brand flag while no domain evidence exists for mh-usa.com.
        brand_mentioned=True,
        mention_position="top",
        mention_count=1,
        competitors_json=[
            {"name": "Grainger", "url": "https://www.grainger.com"},
            {"name": "1 Stop Rack Services", "url": "https://1stoprackservices.com"},
            {"name": "Uline", "url": "https://www.uline.com"},
        ],
        citations_json=["grainger.com", "1stoprackservices.com", "uline.com"],
        sentiment="neutral",
        confidence_score=0.6,
        extraction_model="fake",
        extraction_parse_failed=False,
    )

    payload = _build_aeo_prompt_coverage_payload(profile)
    row = payload["prompts"][0]
    assert row["platforms"]["openai"]["cited"] is False
    assert all(not bool(r.get("is_target")) for r in (row.get("citations_ranking") or []))


@pytest.mark.django_db
def test_prompt_coverage_live_patch_uses_latest_run_visibility_not_global_history():
    pytest.importorskip("stripe")
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    from accounts.models import (
        AEOExecutionRun,
        AEOExtractionSnapshot,
        AEOResponseSnapshot,
        BusinessProfile,
    )

    User = get_user_model()
    user = User.objects.create_user(username="scan_live1", email="scan_live1@example.com", password="pw")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Biz",
        selected_aeo_prompts=["p1", "p2"],
    )

    old_run = AEOExecutionRun.objects.create(
        profile=profile,
        status=AEOExecutionRun.STATUS_COMPLETED,
        extraction_status=AEOExecutionRun.STAGE_COMPLETED,
        scoring_status=AEOExecutionRun.STAGE_COMPLETED,
        recommendation_status=AEOExecutionRun.STAGE_COMPLETED,
    )
    # Historical stale artifact: monitored prompt p2 has a response but no extraction.
    AEOResponseSnapshot.objects.create(
        profile=profile,
        execution_run=old_run,
        prompt_text="p2",
        prompt_hash="h-p2-old",
        raw_response="x",
        platform="openai",
    )

    latest_run = AEOExecutionRun.objects.create(
        profile=profile,
        status=AEOExecutionRun.STATUS_COMPLETED,
        extraction_status=AEOExecutionRun.STAGE_COMPLETED,
        scoring_status=AEOExecutionRun.STAGE_COMPLETED,
        recommendation_status=AEOExecutionRun.STAGE_COMPLETED,
    )
    rsp = AEOResponseSnapshot.objects.create(
        profile=profile,
        execution_run=latest_run,
        prompt_text="p1",
        prompt_hash="h-p1-new",
        raw_response="x",
        platform="openai",
    )
    AEOExtractionSnapshot.objects.create(response_snapshot=rsp, brand_mentioned=False)

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/aeo/prompt-coverage/")
    assert res.status_code == 200
    body = res.json()
    # Banner/live patch should be based on latest run only, so old-run artifacts don't keep it pending.
    assert body.get("visibility_pending") is False


@pytest.mark.django_db
def test_prompt_coverage_live_patch_recomputes_recommendations_pending_from_db(settings):
    pytest.importorskip("stripe")
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    from accounts.models import AEODashboardBundleCache, AEOExecutionRun, BusinessProfile

    settings.AEO_ENABLE_RECOMMENDATION_STAGE = True
    User = get_user_model()
    user = User.objects.create_user(username="scan_live2", email="scan_live2@example.com", password="pw")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Biz",
        selected_aeo_prompts=["p1"],
    )
    AEOExecutionRun.objects.create(
        profile=profile,
        status=AEOExecutionRun.STATUS_COMPLETED,
        scoring_status=AEOExecutionRun.STAGE_COMPLETED,
        recommendation_status=AEOExecutionRun.STAGE_COMPLETED,
    )
    AEODashboardBundleCache.objects.create(
        profile=profile,
        payload_json={
            "prompts": [],
            "recommendations_pending": True,  # stale cached value; live patch should overwrite
            "visibility_pending": False,
        },
    )

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/aeo/prompt-coverage/")
    assert res.status_code == 200
    assert res.json().get("recommendations_pending") is False
