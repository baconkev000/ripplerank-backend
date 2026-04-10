import logging

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from accounts.models import BusinessProfile
from accounts.views import stripe_webhook

User = get_user_model()


class _Obj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.django_db
def test_stripe_webhook_parses_event_object_and_updates_profile(monkeypatch, settings, caplog):
    user = User.objects.create_user(username="wh@example.com", email="wh@example.com", password="x")
    profile = BusinessProfile.objects.create(user=user, is_main=True, business_name="WH")

    event = _Obj(
        id="evt_attr_1",
        type="checkout.session.completed",
        livemode=False,
        api_version="2024-06-20",
        data=_Obj(
            object=_Obj(
                id="cs_test_1",
                object="checkout.session",
                client_reference_id=str(profile.id),
                customer="cus_attr_1",
                subscription="sub_attr_1",
                customer_details=_Obj(email="wh@example.com"),
                payment_link="plink_attr_1",
                invoice="in_attr_1",
            )
        ),
    )

    monkeypatch.setattr("accounts.views.stripe.Webhook.construct_event", lambda *_args, **_kwargs: event)
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    settings.STRIPE_SECRET_KEY = "sk_test"

    req = APIRequestFactory().post(
        "/api/stripe/webhook/",
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="sig_test",
    )
    with caplog.at_level(logging.INFO):
        response = stripe_webhook(req)

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.stripe_customer_id == "cus_attr_1"
    assert profile.stripe_subscription_id == "sub_attr_1"
    assert "stripe.webhook.parsed" in caplog.text
    assert "client_reference_id=" + str(profile.id) in caplog.text
    assert "customer=cus_attr_1" in caplog.text
    assert "subscription=sub_attr_1" in caplog.text


@pytest.mark.django_db
def test_stripe_webhook_parse_failed_returns_400(monkeypatch, settings):
    event = _Obj(id="", type="", livemode=False, api_version="2024-06-20", data=_Obj(object=_Obj()))
    monkeypatch.setattr("accounts.views.stripe.Webhook.construct_event", lambda *_args, **_kwargs: event)
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    settings.STRIPE_SECRET_KEY = "sk_test"

    req = APIRequestFactory().post(
        "/api/stripe/webhook/",
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="sig_test",
    )
    response = stripe_webhook(req)
    assert response.status_code == 400
