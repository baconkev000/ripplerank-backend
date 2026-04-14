from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import BusinessProfileMembership
from .team_invite_email import ensure_placeholder_invite_email_verified


@receiver(post_save, sender=BusinessProfileMembership)
def mark_invited_placeholder_email_verified(
    sender,
    instance: BusinessProfileMembership,
    created: bool,
    **kwargs,
) -> None:
    if not created:
        return
    ensure_placeholder_invite_email_verified(instance.user)
