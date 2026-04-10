import logging

import pytest
from django.contrib.auth import get_user_model

from accounts.models import BusinessProfile
from accounts.stripe_billing import StripeSyncResult
from accounts.stripe_billing import _resolve_profile_for_event
from accounts.stripe_billing import sync_from_checkout_session
from accounts.stripe_billing import sync_from_invoice_paid
from accounts.stripe_billing import sync_from_subscription

User = get_user_model()


@pytest.mark.django_db
def test_resolver_prefers_client_reference_id_when_present():
    user = User.objects.create_user(username="idmatch@example.com", email="idmatch@example.com", password="x")
    profile = BusinessProfile.objects.create(user=user, is_main=True, business_name="Acme")
    payload = {"object": {"client_reference_id": str(profile.id)}}
    resolved, path = _resolve_profile_for_event(payload)
    assert resolved is not None
    assert resolved.id == profile.id
    assert path == "client_reference_id"


@pytest.mark.django_db
def test_resolver_fallback_customer_id_match():
    user = User.objects.create_user(username="cusmatch@example.com", email="cusmatch@example.com", password="x")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Acme",
        stripe_customer_id="cus_123",
    )
    payload = {"object": {"customer": "cus_123"}}
    resolved, path = _resolve_profile_for_event(payload)
    assert resolved is not None
    assert resolved.id == profile.id
    assert path == "customer_id"


@pytest.mark.django_db
def test_resolver_fallback_email_match():
    user = User.objects.create_user(username="emailmatch@example.com", email="emailmatch@example.com", password="x")
    profile = BusinessProfile.objects.create(user=user, is_main=True, business_name="Acme")
    payload = {"object": {"customer_details": {"email": "emailmatch@example.com"}}}
    resolved, path = _resolve_profile_for_event(payload)
    assert resolved is not None
    assert resolved.id == profile.id
    assert path == "email"


@pytest.mark.django_db
def test_checkout_session_logs_mismatch_warning(caplog):
    user_ref = User.objects.create_user(username="ref@example.com", email="ref@example.com", password="x")
    profile_ref = BusinessProfile.objects.create(user=user_ref, is_main=True, business_name="Ref")
    user_other = User.objects.create_user(username="other@example.com", email="other@example.com", password="x")
    BusinessProfile.objects.create(user=user_other, is_main=True, business_name="Other")
    payload = {
        "object": {
            "client_reference_id": str(profile_ref.id),
            "customer_details": {"email": "other@example.com"},
            "customer": "cus_zzz",
            "subscription": "sub_zzz",
        }
    }
    with caplog.at_level(logging.WARNING):
        result = sync_from_checkout_session(payload, event_id="evt_test")
    assert isinstance(result, StripeSyncResult)
    assert result.did_update is True
    assert "checkout session email mismatch" in caplog.text


@pytest.mark.django_db
def test_checkout_session_no_profile_match_returns_diagnostic():
    payload = {"object": {"customer": "cus_missing"}}
    result = sync_from_checkout_session(payload, event_id="evt_missing")
    assert isinstance(result, StripeSyncResult)
    assert result.handled is False
    assert result.did_update is False
    assert result.reason_code == "missing_profile_match"


@pytest.mark.django_db
def test_checkout_session_empty_update_payload_returns_false():
    user = User.objects.create_user(username="empty@example.com", email="empty@example.com", password="x")
    profile = BusinessProfile.objects.create(user=user, is_main=True, business_name="Empty")
    payload = {"object": {"client_reference_id": str(profile.id)}}
    result = sync_from_checkout_session(payload, event_id="evt_empty")
    assert isinstance(result, StripeSyncResult)
    assert result.handled is False
    assert result.did_update is False
    assert result.reason_code == "empty_update_payload"


@pytest.mark.django_db
def test_checkout_session_success_has_updated_fields():
    user = User.objects.create_user(username="ok@example.com", email="ok@example.com", password="x")
    profile = BusinessProfile.objects.create(user=user, is_main=True, business_name="Ok")
    payload = {
        "object": {
            "client_reference_id": str(profile.id),
            "customer": "cus_ok",
            "subscription": "sub_ok",
        }
    }
    result = sync_from_checkout_session(payload, event_id="evt_ok")
    assert isinstance(result, StripeSyncResult)
    assert result.handled is True
    assert result.did_update is True
    assert len(result.updated_fields) > 0


@pytest.mark.django_db
def test_invoice_paid_updates_via_email_fallback_and_lines_price():
    user = User.objects.create_user(username="inv-email@example.com", email="inv-email@example.com", password="x")
    profile = BusinessProfile.objects.create(user=user, is_main=True, business_name="Inv Email")
    payload = {
        "object": {
            "customer": "cus_invoice_email",
            "subscription": "sub_invoice_email",
            "customer_details": {"email": "inv-email@example.com"},
            "lines": {"data": [{"price": {"id": "price_line_123"}}]},
        }
    }
    result = sync_from_invoice_paid(payload, event_id="evt_invoice_email")
    assert isinstance(result, StripeSyncResult)
    assert result.handled is True
    assert result.did_update is True
    assert "stripe_price_id" in result.updated_fields
    profile.refresh_from_db()
    assert profile.stripe_customer_id == "cus_invoice_email"
    assert profile.stripe_subscription_id == "sub_invoice_email"
    assert profile.stripe_price_id == "price_line_123"
    assert profile.stripe_subscription_status == "active"


@pytest.mark.django_db
def test_subscription_updated_reads_items_price_id():
    user = User.objects.create_user(username="sub@example.com", email="sub@example.com", password="x")
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Sub",
        stripe_customer_id="cus_sub_123",
    )
    payload = {
        "object": {
            "id": "sub_123",
            "customer": "cus_sub_123",
            "status": "active",
            "cancel_at_period_end": False,
            "current_period_end": 1735689600,
            "items": {"data": [{"price": {"id": "price_sub_123"}}]},
        }
    }
    result = sync_from_subscription(payload, event_id="evt_sub_updated")
    assert isinstance(result, StripeSyncResult)
    assert result.handled is True
    assert result.did_update is True
    assert "stripe_price_id" in result.updated_fields
    profile.refresh_from_db()
    assert profile.stripe_subscription_id == "sub_123"
    assert profile.stripe_price_id == "price_sub_123"
    assert profile.stripe_subscription_status == "active"


@pytest.mark.django_db
def test_invoice_paid_empty_update_payload_returns_reason():
    user = User.objects.create_user(username="inv-empty@example.com", email="inv-empty@example.com", password="x")
    profile = BusinessProfile.objects.create(user=user, is_main=True, business_name="InvEmpty")
    payload = {"object": {"customer_details": {"email": "inv-empty@example.com"}}}
    result = sync_from_invoice_paid(payload, event_id="evt_inv_empty")
    assert isinstance(result, StripeSyncResult)
    assert result.handled is False
    assert result.did_update is False
    assert result.matched_profile_id == profile.id
    assert result.reason_code == "empty_update_payload"

