import pytest
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

from accounts.models import BusinessProfile, BusinessProfileMembership

User = get_user_model()


@pytest.mark.django_db
def test_team_membership_marks_placeholder_user_email_verified():
    owner = User.objects.create_user(username="own", email="own@example.com", password="pw")
    bp = BusinessProfile.objects.create(user=owner, is_main=True, business_name="Co")

    invited = User(username="inv@example.com", email="inv@example.com")
    invited.set_unusable_password()
    invited.save()

    assert not EmailAddress.objects.filter(user=invited).exists()

    BusinessProfileMembership.objects.create(
        business_profile=bp,
        user=invited,
        role=BusinessProfileMembership.ROLE_MEMBER,
        is_owner=False,
    )

    addr = EmailAddress.objects.get(user=invited)
    assert addr.email == "inv@example.com"
    assert addr.verified is True
    assert addr.primary is True


@pytest.mark.django_db
def test_team_membership_does_not_force_verify_for_users_with_password():
    owner = User.objects.create_user(username="own2", email="own2@example.com", password="pw")
    bp = BusinessProfile.objects.create(user=owner, is_main=True, business_name="Co2")

    member = User.objects.create_user(
        username="mem@example.com",
        email="mem@example.com",
        password="secret12",
    )
    EmailAddress.objects.create(
        user=member,
        email="mem@example.com",
        verified=False,
        primary=True,
    )

    BusinessProfileMembership.objects.create(
        business_profile=bp,
        user=member,
        role=BusinessProfileMembership.ROLE_MEMBER,
        is_owner=False,
    )

    addr = EmailAddress.objects.get(user=member)
    assert addr.verified is False
