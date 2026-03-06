from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from django.conf import settings

from .models import GoogleAdsConnection, GoogleAdsKeywordIdea

logger = logging.getLogger(__name__)


@dataclass
class KeywordIdea:
    keyword: str
    avg_monthly_searches: int | None
    competition: str | None
    competition_index: int | None
    low_top_of_page_bid_micros: int | None
    high_top_of_page_bid_micros: int | None


def _has_app_ads_credentials() -> bool:
    """App-level credentials (developer token, OAuth client). Refresh token comes from user auth."""
    required = [
        "GOOGLE_ADS_DEVELOPER_TOKEN",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
    ]
    return all(getattr(settings, name, None) for name in required)


def classify_intent(keyword: str) -> str:
    """
    Simple rule-based intent classification.
    Does not rely on Google Ads-provided intent.
    """
    k = keyword.lower()
    high_triggers = [
        "buy",
        "price",
        "cost",
        "near me",
        "coupon",
        "deal",
        "best",
        "hire",
        "book",
        "quote",
        "service",
    ]
    low_triggers = [
        "what is",
        "definition",
        "how to",
        "tutorial",
        "examples",
        "guide",
        "meaning",
    ]

    if any(t in k for t in high_triggers):
        return "HIGH"
    if any(t in k for t in low_triggers):
        return "LOW"
    return "MEDIUM"


def fetch_keyword_ideas_for_user(
    user_id: int,
    keywords: Iterable[str],
    cache_ttl_days: int = 7,
    industry: str | None = None,
    description: str | None = None,
) -> dict[str, KeywordIdea]:
    """
    Fetch keyword ideas from Google Ads KeywordPlanIdeaService for the given user & keywords.

    Results are cached per user/keyword in GoogleAdsKeywordIdea to reduce API calls.
    If Google Ads credentials are missing, this returns only cached data.
    """
    from google.ads.googleads.client import GoogleAdsClient  # type: ignore[import]

    keywords_list = list(keywords)
    logger.info(
        "[Google Ads] fetch_keyword_ideas_for_user: user_id=%s, keywords_count=%s, industry=%s, description_len=%s",
        user_id,
        len(keywords_list),
        industry or "(none)",
        len(description) if description else 0,
    )

    now = datetime.now(timezone.utc)

    # First, load cached ideas.
    cached: dict[str, KeywordIdea] = {}
    fresh_cutoff = now - timedelta(days=cache_ttl_days)

    for idea in GoogleAdsKeywordIdea.objects.filter(
        user_id=user_id, last_fetched_at__gte=fresh_cutoff
    ):
        cached[idea.keyword] = KeywordIdea(
            keyword=idea.keyword,
            avg_monthly_searches=idea.avg_monthly_searches,
            competition=idea.competition,
            competition_index=idea.competition_index,
            low_top_of_page_bid_micros=idea.low_top_of_page_bid_micros,
            high_top_of_page_bid_micros=idea.high_top_of_page_bid_micros,
        )

    remaining = [k for k in keywords_list if k not in cached]
    logger.info(
        "[Google Ads] Cached ideas loaded: %s; remaining keywords to fetch: %s",
        len(cached),
        len(remaining),
    )

    # Use business profile context (industry / description) as additional seeds
    # to help Google Ads suggest better ideas, without changing intent logic.
    extra_seeds: list[str] = []
    if industry:
        extra_seeds.append(industry)
    if description:
        # Take a short prefix of the description as a seed (avoid flooding the request).
        snippet = description.strip()
        if len(snippet) > 80:
            snippet = snippet[:80]
        if snippet:
            extra_seeds.append(snippet)

    has_app_creds = _has_app_ads_credentials()
    logger.info(
        "[Google Ads] App credentials present: %s; remaining=%s, extra_seeds=%s",
        has_app_creds,
        len(remaining),
        extra_seeds,
    )

    if (not remaining and not extra_seeds) or not has_app_creds:
        logger.info(
            "[Google Ads] Early return (no seeds or no app creds). Returning %s cached.",
            len(cached),
        )
        return cached

    # Use the user's Google Ads connection (refresh_token + customer_id from OAuth at login).
    # Do not use env for refresh token — it comes from user auth only.
    try:
        conn = GoogleAdsConnection.objects.get(user_id=user_id)
        logger.info(
            "[Google Ads] User connection found: user_id=%s, has_refresh_token=%s, customer_id=%s",
            user_id,
            bool((conn.refresh_token or "").strip()),
            (conn.customer_id or "").strip() or "(empty)",
        )
    except GoogleAdsConnection.DoesNotExist:
        logger.warning("[Google Ads] No GoogleAdsConnection for user_id=%s. Returning cached only.", user_id)
        return cached
    refresh_token = (conn.refresh_token or "").strip()
    customer_id = (conn.customer_id or "").strip()
    if not customer_id:
        customer_id = (getattr(settings, "GOOGLE_ADS_CUSTOMER_ID", None) or "").strip()
        if customer_id:
            logger.info("[Google Ads] Using GOOGLE_ADS_CUSTOMER_ID from settings (user connection had no customer_id).")
    if not refresh_token or not customer_id:
        logger.warning(
            "[Google Ads] User connection missing refresh_token or customer_id (refresh_token=%s, customer_id=%s). Returning cached.",
            "present" if refresh_token else "missing",
            customer_id or "missing",
        )
        return cached

    # Build Google Ads client using user's tokens and app-level developer token + OAuth client.
    config = {
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "login_customer_id": customer_id.replace("-", ""),
        "client_customer_id": customer_id.replace("-", ""),
        "use_proto_plus": True,
        "refresh_token": refresh_token,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
    }
    customer_id_clean = customer_id.replace("-", "")
    request_seeds = remaining + extra_seeds
    logger.info(
        "[Google Ads] Calling KeywordPlanIdeaService: customer_id=%s, seed_count=%s, seeds=%s",
        customer_id_clean,
        len(request_seeds),
        request_seeds[:10] if len(request_seeds) > 10 else request_seeds,
    )

    client = GoogleAdsClient.load_from_dict(config)
    service = client.get_service("KeywordPlanIdeaService")

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = customer_id_clean
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
    # Always include the remaining keywords; optionally add extra business-context seeds.
    if remaining:
        request.keyword_seed.keywords.extend(remaining)
    if extra_seeds:
        request.keyword_seed.keywords.extend(extra_seeds)

    try:
        response = service.generate_keyword_ideas(request=request)
        response_list = list(response)
        logger.info("[Google Ads] API returned %s keyword ideas.", len(response_list))
    except Exception as e:
        logger.exception(
            "[Google Ads] KeywordPlanIdeaService.generate_keyword_ideas failed: %s. Returning cached.",
            e,
        )
        return cached

    added = 0
    # When remaining is empty we're in "recommendation only" mode (seeds from
    # industry/description): accept all ideas from the API. Otherwise only
    # keep ideas that match the requested seed keywords.
    for idea in response_list:
        text = idea.text
        if remaining and text not in remaining:
            continue

        metrics = idea.keyword_idea_metrics
        avg_monthly_searches = (
            int(metrics.avg_monthly_searches) if metrics.avg_monthly_searches else None
        )
        competition_enum = metrics.competition.name if metrics.competition else None
        competition_index = (
            int(metrics.competition_index) if metrics.competition_index else None
        )
        low_bid = (
            int(metrics.low_top_of_page_bid_micros)
            if metrics.low_top_of_page_bid_micros
            else None
        )
        high_bid = (
            int(metrics.high_top_of_page_bid_micros)
            if metrics.high_top_of_page_bid_micros
            else None
        )

        obj, _ = GoogleAdsKeywordIdea.objects.update_or_create(
            user_id=user_id,
            keyword=text,
            defaults={
                "avg_monthly_searches": avg_monthly_searches or 0,
                "competition": competition_enum or "",
                "competition_index": competition_index or 0,
                "low_top_of_page_bid_micros": low_bid or 0,
                "high_top_of_page_bid_micros": high_bid or 0,
                "last_fetched_at": now,
            },
        )

        cached[text] = KeywordIdea(
            keyword=text,
            avg_monthly_searches=avg_monthly_searches,
            competition=competition_enum,
            competition_index=competition_index,
            low_top_of_page_bid_micros=low_bid,
            high_top_of_page_bid_micros=high_bid,
        )
        added += 1

    logger.info(
        "[Google Ads] fetch_keyword_ideas_for_user done: user_id=%s, ideas_added_from_api=%s, total_cached=%s.",
        user_id,
        added,
        len(cached),
    )
    return cached


@dataclass
class AdsMetrics:
    """Campaign performance metrics for the Ads Agent overview."""

    new_customers_this_month: int
    new_customers_previous_month: int
    avg_roas: float
    google_search_roas: float
    cost_per_customer: float
    cost_per_customer_previous: float
    active_campaigns_count: int


def fetch_ads_metrics_for_user_result(
    user_id: int,
) -> tuple[AdsMetrics | None, str | None, str | None]:
    """
    Fetch Google Ads campaign metrics for the current user.

    Returns (metrics, reason_code, detail_message).
    - If success: (AdsMetrics, None, None).
    - If failure: (None, reason, detail). reason is one of:
      not_connected, missing_refresh_token, missing_customer_id, api_error.
    """
    if not _has_app_ads_credentials():
        logger.info("[Google Ads] fetch_ads_metrics_for_user: app credentials missing.")
        return (
            None,
            "api_error",
            "Google Ads integration is not fully configured. Please contact support.",
        )

    try:
        conn = GoogleAdsConnection.objects.get(user_id=user_id)
    except GoogleAdsConnection.DoesNotExist:
        logger.warning("[Google Ads] No GoogleAdsConnection for user_id=%s.", user_id)
        return (
            None,
            "not_connected",
            "Google Ads is not connected. Connect your account in Integrations to see metrics.",
        )

    refresh_token = (conn.refresh_token or "").strip()
    customer_id = (conn.customer_id or "").strip()
    if not customer_id:
        customer_id = (getattr(settings, "GOOGLE_ADS_CUSTOMER_ID", None) or "").strip()

    if not refresh_token:
        logger.warning("[Google Ads] User connection missing refresh_token.")
        return (
            None,
            "missing_refresh_token",
            "Your Google Ads connection is missing authorization. Please disconnect and reconnect Google Ads in Integrations.",
        )
    if not customer_id:
        logger.warning("[Google Ads] User connection missing customer_id.")
        return (
            None,
            "missing_customer_id",
            "We couldn't determine your Google Ads account. Please disconnect and reconnect Google Ads in Integrations, and ensure you have access to at least one Google Ads account.",
        )

    customer_id_clean = customer_id.replace("-", "")
    config = {
        "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
        "login_customer_id": customer_id_clean,
        "client_customer_id": customer_id_clean,
        "use_proto_plus": True,
        "refresh_token": refresh_token,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
    }

    try:
        from google.ads.googleads.client import GoogleAdsClient  # type: ignore[import]

        client = GoogleAdsClient.load_from_dict(config)
        ga_service = client.get_service("GoogleAdsService")

        def _run_query(query: str) -> list:
            response = ga_service.search(customer_id=customer_id_clean, query=query)
            return list(response)

        # This month: customer-level totals (conversions, cost, value)
        q_this = """
            SELECT
                metrics.conversions,
                metrics.cost_micros,
                metrics.conversions_value
            FROM customer
            WHERE segments.date DURING THIS_MONTH
        """
        # Previous month
        q_prev = """
            SELECT
                metrics.conversions,
                metrics.cost_micros,
                metrics.conversions_value
            FROM customer
            WHERE segments.date DURING LAST_MONTH
        """
        # This month: Search campaigns only (for Google Search ROAS)
        q_search = """
            SELECT
                metrics.conversions,
                metrics.cost_micros,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date DURING THIS_MONTH
              AND campaign.advertising_channel_type = 'SEARCH'
        """
        # Count distinct campaigns with any cost this month (for "X Active" badge)
        q_active_campaigns = """
            SELECT campaign.id
            FROM campaign
            WHERE segments.date DURING THIS_MONTH
              AND metrics.cost_micros > 0
        """

        def _sum_row(row) -> tuple[int, int, int]:
            m = row.metrics
            conv = int(m.conversions) if m.conversions else 0
            cost = int(m.cost_micros) if m.cost_micros else 0
            val = int(m.conversions_value) if m.conversions_value else 0
            return conv, cost, val

        rows_this = _run_query(q_this)
        rows_prev = _run_query(q_prev)
        rows_search = _run_query(q_search)

        conv_this = cost_this = val_this = 0
        for row in rows_this:
            c, co, v = _sum_row(row)
            conv_this += c
            cost_this += co
            val_this += v

        conv_prev = cost_prev = val_prev = 0
        for row in rows_prev:
            c, co, v = _sum_row(row)
            conv_prev += c
            cost_prev += co
            val_prev += v

        conv_search = cost_search = val_search = 0
        for row in rows_search:
            c, co, v = _sum_row(row)
            conv_search += c
            cost_search += co
            val_search += v

        # ROAS = conversions_value / cost (both in micros → dimensionless)
        avg_roas = (val_this / cost_this) if cost_this else 0.0
        google_search_roas = (val_search / cost_search) if cost_search else 0.0
        # Cost per customer in currency (cost_micros / 1e6 / conversions)
        cost_per_customer = (cost_this / 1_000_000 / conv_this) if conv_this else 0.0
        cost_per_customer_previous = (cost_prev / 1_000_000 / conv_prev) if conv_prev else 0.0

        # Distinct campaigns with spend this month
        rows_active = _run_query(q_active_campaigns)
        active_campaign_ids: set[int] = set()
        for row in rows_active:
            if hasattr(row, "campaign") and row.campaign and row.campaign.id:
                active_campaign_ids.add(int(row.campaign.id))
        active_campaigns_count = len(active_campaign_ids)

        return (
            AdsMetrics(
                new_customers_this_month=conv_this,
                new_customers_previous_month=conv_prev,
                avg_roas=round(avg_roas, 2),
                google_search_roas=round(google_search_roas, 2),
                cost_per_customer=round(cost_per_customer, 2),
                cost_per_customer_previous=round(cost_per_customer_previous, 2),
                active_campaigns_count=active_campaigns_count,
            ),
            None,
            None,
        )
    except Exception as e:
        logger.exception("[Google Ads] fetch_ads_metrics_for_user failed: %s", e)
        err_msg = str(e).strip() or "Unknown error"
        return (
            None,
            "api_error",
            f"Google Ads API error: {err_msg}. Check that your account has access to Google Ads and try reconnecting in Integrations.",
        )


def fetch_ads_metrics_for_user(user_id: int) -> AdsMetrics | None:
    """Convenience wrapper that returns only metrics or None (for callers that don't need reason)."""
    metrics, _reason, _detail = fetch_ads_metrics_for_user_result(user_id)
    return metrics

