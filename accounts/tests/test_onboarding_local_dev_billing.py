import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import BusinessProfile

User = get_user_model()


@pytest.mark.django_db
def test_local_dev_billing_complete_returns_404_when_debug_off(settings):
    settings.DEBUG = False
    settings.ALLOW_ONBOARDING_BILLING_BYPASS = False
    user = User.objects.create_user(username="ldb1@example.com", email="ldb1@example.com", password="x")
    BusinessProfile.objects.create(user=user, is_main=True, business_name="A")
    client = APIClient()
    client.force_authenticate(user=user)
    res = client.post("/api/onboarding/local-dev-billing-complete/", {"plan": "pro"}, format="json")
    assert res.status_code == 404


@pytest.mark.django_db
def test_local_dev_billing_complete_sets_fake_stripe_when_bypass_flag_on_debug_off(settings):
    settings.DEBUG = False
    settings.ALLOW_ONBOARDING_BILLING_BYPASS = True
    user = User.objects.create_user(username="ldb3@example.com", email="ldb3@example.com", password="x")
    BusinessProfile.objects.create(user=user, is_main=True, business_name="C")
    client = APIClient()
    client.force_authenticate(user=user)
    res = client.post("/api/onboarding/local-dev-billing-complete/", {"plan": "advanced"}, format="json")
    assert res.status_code == 200
    assert res.json().get("ok") is True
    p = BusinessProfile.objects.get(user=user, is_main=True)
    assert p.stripe_customer_id == "cus_local_dev"
    assert p.stripe_subscription_id == "sub_local_dev"
    assert p.stripe_subscription_status == "active"
    assert p.plan == BusinessProfile.PLAN_ADVANCED


@pytest.mark.django_db
def test_local_dev_billing_complete_sets_fake_stripe_when_debug_on(settings):
    settings.DEBUG = True
    user = User.objects.create_user(username="ldb2@example.com", email="ldb2@example.com", password="x")
    BusinessProfile.objects.create(user=user, is_main=True, business_name="B")
    client = APIClient()
    client.force_authenticate(user=user)
    res = client.post("/api/onboarding/local-dev-billing-complete/", {"plan": "advanced"}, format="json")
    assert res.status_code == 200
    assert res.json().get("ok") is True
    p = BusinessProfile.objects.get(user=user, is_main=True)
    assert p.stripe_customer_id == "cus_local_dev"
    assert p.stripe_subscription_id == "sub_local_dev"
    assert p.stripe_subscription_status == "active"
    assert p.plan == BusinessProfile.PLAN_ADVANCED


@pytest.mark.django_db
def test_local_dev_billing_complete_enqueues_post_payment_seo_when_website_present(
    settings, monkeypatch, django_capture_on_commit_callbacks,
):
    settings.DEBUG = True
    enqueued: list[int] = []

    def _fake_delay(profile_id: int) -> None:
        enqueued.append(int(profile_id))

    monkeypatch.setattr(
        "accounts.tasks.post_payment_seo_snapshot_task.delay",
        _fake_delay,
    )
    user = User.objects.create_user(username="ldbseo@example.com", email="ldbseo@example.com", password="x")
    BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="WithSite",
        website_url="https://ldbseo.example.com",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    with django_capture_on_commit_callbacks(execute=True):
        res = client.post("/api/onboarding/local-dev-billing-complete/", {"plan": "pro"}, format="json")
    assert res.status_code == 200
    assert enqueued == [BusinessProfile.objects.get(user=user, is_main=True).id]
