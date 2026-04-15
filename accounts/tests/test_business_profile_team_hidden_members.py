import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import BusinessProfile, BusinessProfileMembership

User = get_user_model()


@pytest.mark.django_db
def test_team_get_hides_membership_rows_marked_hidden_from_team_ui():
    owner = User.objects.create_user(username="owner_hidden", email="owner_hidden@example.com", password="pw")
    visible_user = User.objects.create_user(
        username="visible_hidden", email="visible_hidden@example.com", password="pw"
    )
    hidden_user = User.objects.create_user(
        username="hidden_hidden", email="hidden_hidden@example.com", password="pw"
    )
    profile = BusinessProfile.objects.create(user=owner, is_main=True, business_name="Hidden Team Biz")

    BusinessProfileMembership.objects.create(
        business_profile=profile,
        user=visible_user,
        role=BusinessProfileMembership.ROLE_ADMIN,
        is_owner=False,
        hidden_from_team_ui=False,
    )
    BusinessProfileMembership.objects.create(
        business_profile=profile,
        user=hidden_user,
        role=BusinessProfileMembership.ROLE_ADMIN,
        is_owner=False,
        hidden_from_team_ui=True,
    )

    client = APIClient()
    client.force_authenticate(user=owner)
    res = client.get("/api/business-profile/team/")
    assert res.status_code == 200
    body = res.json()
    emails = [str(m.get("email") or "").strip().lower() for m in body.get("members", [])]
    assert "visible_hidden@example.com" in emails
    assert "hidden_hidden@example.com" not in emails


@pytest.mark.django_db
def test_hidden_membership_still_grants_profile_access():
    owner = User.objects.create_user(username="owner_access", email="owner_access@example.com", password="pw")
    hidden_user = User.objects.create_user(
        username="hidden_access", email="hidden_access@example.com", password="pw"
    )
    profile = BusinessProfile.objects.create(user=owner, is_main=True, business_name="Hidden Access Biz")
    BusinessProfileMembership.objects.create(
        business_profile=profile,
        user=hidden_user,
        role=BusinessProfileMembership.ROLE_ADMIN,
        is_owner=False,
        hidden_from_team_ui=True,
    )

    client = APIClient()
    client.force_authenticate(user=hidden_user)
    # Hidden row should still resolve workspace access to team endpoint.
    res_team = client.get("/api/business-profile/team/")
    assert res_team.status_code == 200
    emails = [str(m.get("email") or "").strip().lower() for m in res_team.json().get("members", [])]
    assert "hidden_access@example.com" not in emails

