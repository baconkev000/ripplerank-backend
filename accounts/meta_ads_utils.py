from __future__ import annotations

"""
Utility functions for Meta Ads integrations.

These are intentionally lightweight scaffolds so that Meta Ads can be wired
into the same integration/status surface area as Google Ads. The actual
OAuth flow, token storage, and reporting logic can be implemented here
later without changing the public API exposed from views.py.
"""

from dataclasses import dataclass


@dataclass
class MetaAdsStatus:
    """
    Simple status payload indicating whether the current user has a usable
    Meta Ads connection.
    """

    connected: bool = False


def get_meta_ads_status_for_user(user_id: int) -> MetaAdsStatus:
    """
    Return whether the given user has an active Meta Ads connection.

    For now this is a stub that always returns ``connected=False`` so that
    the rest of the application can depend on a stable API surface. When
    Meta Ads is fully implemented, this function should be updated to read
    from the appropriate connection model and/or external API.
    """

    # TODO: implement real Meta Ads connection lookup.
    return MetaAdsStatus(connected=False)

