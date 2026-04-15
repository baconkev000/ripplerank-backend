import pytest
from rest_framework import serializers
from django.contrib.auth import get_user_model

from accounts.serializers import BusinessProfileSerializer, _normalize_stored_website_url
from accounts.models import BusinessProfile


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com"),
        ("https://Example.com/foo/bar?x=1#h", "https://example.com"),
        ("www.acme.org/path", "https://acme.org"),
        ("https://user:pass@shop.example.com/checkout", "https://shop.example.com"),
        ("http://localhost:3000/app", "http://localhost:3000"),
        ("https://example.com/" + "a" * 300, "https://example.com"),
    ],
)
def test_normalize_stored_website_url_strips_path_and_query(raw, expected):
    assert _normalize_stored_website_url(raw) == expected


def test_normalize_stored_website_url_empty():
    assert _normalize_stored_website_url("") == ""
    assert _normalize_stored_website_url("   ") == ""


def test_business_profile_serializer_validate_website_url_delegates_to_normalize():
    ser = BusinessProfileSerializer()
    assert ser.validate_website_url("https://x.test/p?q=1") == "https://x.test"
    with pytest.raises(serializers.ValidationError):
        ser.validate_website_url("https:///")


@pytest.mark.django_db
def test_business_profile_serializer_requires_state_when_local_customer_reach():
    user = get_user_model().objects.create_user(
        username="reach-local",
        email="reach-local@example.com",
        password="pw",
    )
    profile = BusinessProfile.objects.create(user=user, is_main=True, customer_reach="online")

    ser = BusinessProfileSerializer(
        profile,
        data={"customer_reach": "local", "customer_reach_state": ""},
        partial=True,
    )
    assert not ser.is_valid()
    assert "customer_reach_state" in ser.errors


@pytest.mark.django_db
def test_business_profile_serializer_clears_local_fields_when_online_customer_reach():
    user = get_user_model().objects.create_user(
        username="reach-online",
        email="reach-online@example.com",
        password="pw",
    )
    profile = BusinessProfile.objects.create(
        user=user,
        is_main=True,
        customer_reach="local",
        customer_reach_state="CA",
        customer_reach_city="San Diego",
    )

    ser = BusinessProfileSerializer(
        profile,
        data={"customer_reach": "online"},
        partial=True,
    )
    assert ser.is_valid(), ser.errors
    updated = ser.save()
    assert updated.customer_reach == "online"
    assert updated.customer_reach_state == ""
    assert updated.customer_reach_city == ""
