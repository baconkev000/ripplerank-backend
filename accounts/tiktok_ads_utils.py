from __future__ import annotations

"""
Utility functions for TikTok Ads integrations.

These mirror the Meta Ads utilities and provide a stable place to add
real TikTok Ads OAuth and reporting logic later, while keeping the
HTTP API in views.py simple.
"""

from dataclasses import dataclass


@dataclass
class TikTokAdsStatus:
    """
    Simple status payload indicating whether the current user has a usable
    TikTok Ads connection.
    """

    connected: bool = False


def get_tiktok_ads_status_for_user(user_id: int) -> TikTokAdsStatus:
    """
    Return whether the given user has an active TikTok Ads connection.

    Currently this is a stub that always returns ``connected=False``.
    When TikTok Ads integration is implemented, update this function to
    read from the appropriate connection model and/or external API.
    """

    # TODO: implement real TikTok Ads connection lookup.
    return TikTokAdsStatus(connected=False)

