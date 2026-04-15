import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import BusinessProfile

User = get_user_model()


def _mk_user_profile() -> tuple[object, BusinessProfile]:
    user = User.objects.create_user(
        username="bill_pm@example.com",
        email="bill_pm@example.com",
        password="pw",
    )
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        business_name="Billing Co",
        stripe_customer_id="cus_test_pm",
        stripe_subscription_id="sub_test_pm",
        plan=BusinessProfile.PLAN_PRO,
    )
    return user, profile


@pytest.mark.django_db
def test_billing_summary_payment_method_from_subscription_default(monkeypatch, settings):
    pytest.importorskip("stripe")
    settings.STRIPE_SECRET_KEY = "sk_test_123"
    user, _profile = _mk_user_profile()

    monkeypatch.setattr(
        "accounts.views.stripe.Subscription.retrieve",
        lambda *_a, **_k: {
            "items": {
                "data": [
                    {
                        "price": {
                            "unit_amount": 4900,
                            "currency": "usd",
                            "recurring": {"interval": "month", "interval_count": 1},
                        }
                    }
                ]
            },
            "default_payment_method": {
                "card": {
                    "brand": "visa",
                    "last4": "4242",
                    "exp_month": 9,
                    "exp_year": 2029,
                    "funding": "credit",
                }
            },
        },
    )
    monkeypatch.setattr("accounts.views.stripe.Subscription.list", lambda *_a, **_k: {"data": []})
    monkeypatch.setattr("accounts.views.stripe.Customer.retrieve", lambda *_a, **_k: {})
    monkeypatch.setattr("accounts.views.stripe.Invoice.list", lambda *_a, **_k: {"data": []})
    monkeypatch.setattr("accounts.views.stripe.PaymentMethod.retrieve", lambda *_a, **_k: {})
    monkeypatch.setattr("accounts.views.stripe.PaymentIntent.retrieve", lambda *_a, **_k: {})

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/billing/summary/")
    assert res.status_code == 200
    body = res.json()
    assert body["payment_method"] == {
        "brand": "visa",
        "last4": "4242",
        "exp_month": 9,
        "exp_year": 2029,
        "funding": "credit",
    }
    assert "invoices" in body
    assert "plan_label" in body


@pytest.mark.django_db
def test_billing_summary_payment_method_falls_back_to_customer_default(monkeypatch, settings):
    pytest.importorskip("stripe")
    settings.STRIPE_SECRET_KEY = "sk_test_123"
    user, _profile = _mk_user_profile()

    monkeypatch.setattr(
        "accounts.views.stripe.Subscription.retrieve",
        lambda *_a, **_k: {
            "items": {
                "data": [
                    {
                        "price": {
                            "unit_amount": 4900,
                            "currency": "usd",
                            "recurring": {"interval": "month", "interval_count": 1},
                        }
                    }
                ]
            },
            "default_payment_method": None,
        },
    )
    monkeypatch.setattr("accounts.views.stripe.Subscription.list", lambda *_a, **_k: {"data": []})
    monkeypatch.setattr(
        "accounts.views.stripe.Customer.retrieve",
        lambda *_a, **_k: {
            "invoice_settings": {
                "default_payment_method": {
                    "card": {
                        "brand": "mastercard",
                        "last4": "4444",
                        "exp_month": 12,
                        "exp_year": 2030,
                        "funding": "debit",
                    }
                }
            }
        },
    )
    monkeypatch.setattr("accounts.views.stripe.Invoice.list", lambda *_a, **_k: {"data": []})
    monkeypatch.setattr("accounts.views.stripe.PaymentMethod.retrieve", lambda *_a, **_k: {})
    monkeypatch.setattr("accounts.views.stripe.PaymentIntent.retrieve", lambda *_a, **_k: {})

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/billing/summary/")
    assert res.status_code == 200
    body = res.json()
    assert body["payment_method"] == {
        "brand": "mastercard",
        "last4": "4444",
        "exp_month": 12,
        "exp_year": 2030,
        "funding": "debit",
    }


@pytest.mark.django_db
def test_billing_summary_payment_method_null_when_missing_everywhere(monkeypatch, settings):
    pytest.importorskip("stripe")
    settings.STRIPE_SECRET_KEY = "sk_test_123"
    user, _profile = _mk_user_profile()

    monkeypatch.setattr(
        "accounts.views.stripe.Subscription.retrieve",
        lambda *_a, **_k: {"items": {"data": []}, "default_payment_method": None},
    )
    monkeypatch.setattr("accounts.views.stripe.Subscription.list", lambda *_a, **_k: {"data": []})
    monkeypatch.setattr(
        "accounts.views.stripe.Customer.retrieve",
        lambda *_a, **_k: {"invoice_settings": {"default_payment_method": None}},
    )
    monkeypatch.setattr(
        "accounts.views.stripe.Invoice.list",
        lambda *_a, **_k: {"data": [{"status": "paid", "payment_intent": None}]},
    )
    monkeypatch.setattr("accounts.views.stripe.PaymentMethod.retrieve", lambda *_a, **_k: {})
    monkeypatch.setattr("accounts.views.stripe.PaymentIntent.retrieve", lambda *_a, **_k: {})

    client = APIClient()
    client.force_authenticate(user=user)
    res = client.get("/api/billing/summary/")
    assert res.status_code == 200
    body = res.json()
    assert body["payment_method"] is None
