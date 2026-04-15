import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import BusinessProfile

User = get_user_model()


@pytest.mark.django_db
def test_business_profile_list_post_reuses_existing_profile_for_same_domain():
    user = User.objects.create_user(username="dedup", email="dedup@example.com", password="pw")
    existing = BusinessProfile.objects.create(
        user=user,
        business_name="Acme",
        website_url="https://example.com",
        is_main=True,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        "/api/business-profiles/",
        {
            "business_name": "Acme copy",
            "website_url": "https://www.example.com/",
            "business_address": "NYC",
        },
        format="json",
    )

    assert resp.status_code == 200
    assert resp.data["id"] == existing.id
    assert BusinessProfile.objects.filter(user=user).count() == 1
