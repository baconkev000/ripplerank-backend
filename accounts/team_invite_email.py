"""Helpers for team-invited users (placeholder accounts, no outbound email yet)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


def ensure_placeholder_invite_email_verified(user: AbstractBaseUser) -> None:
    """
    Team invites use ``set_unusable_password()``; mark the primary email as verified so
    django-allauth does not send users to ``/accounts/confirm-email/`` when they use Google
    or other OAuth (and if email verification is tightened later, invited rows stay consistent).
    """
    if not user or not getattr(user, "pk", None):
        return
    if user.has_usable_password():
        return
    email = (getattr(user, "email", None) or "").strip().lower()
    if not email or "@" not in email:
        return

    from allauth.account.models import EmailAddress

    qs = EmailAddress.objects.filter(user=user)
    match = qs.filter(email__iexact=email).first()
    qs.update(primary=False)
    if match is not None:
        match.email = email
        match.verified = True
        match.primary = True
        match.save(
            update_fields=["email", "verified", "primary"],
        )
    else:
        EmailAddress.objects.create(
            user=user,
            email=email,
            verified=True,
            primary=True,
        )
