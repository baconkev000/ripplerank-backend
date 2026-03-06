import logging
import secrets
from urllib.parse import urlencode, unquote, quote
from datetime import datetime, date, timedelta, timezone

import requests
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout as django_logout
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    AgentActivityLog,
    BusinessProfile,
    GoogleAdsMetricsCache,
    GoogleSearchConsoleConnection,
    GoogleBusinessProfileConnection,
    SEOOverviewSnapshot,
    ReviewsOverviewSnapshot,
    AgentConversation,
    AgentMessage,
)

# Third-party API cache: only refetch from GSC, Google Ads, GBP if last fetch was >= this long ago.
THIRD_PARTY_CACHE_TTL = timedelta(hours=1)
from .serializers import BusinessProfileSerializer
from .google_ads_client import (
    classify_intent,
    fetch_ads_metrics_for_user,
    fetch_ads_metrics_for_user_result,
    fetch_keyword_ideas_for_user,
)
from .meta_ads_utils import get_meta_ads_status_for_user
from .tiktok_ads_utils import get_tiktok_ads_status_for_user
from . import openai_utils

logger = logging.getLogger(__name__)
User = get_user_model()


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    Use Django session auth without enforcing CSRF.

    This is safe here because the API is only accessible to already
    authenticated users and is called via our own frontend.
    """

    def enforce_csrf(self, request):
        return  # Skip the CSRF check performed by SessionAuthentication.


def health_check(_: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def google_login(request: HttpRequest) -> HttpResponse:
    state = secrets.token_urlsafe(32)
    frontend_base = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")

    # Allow the frontend to pass either an absolute next URL or a relative path.
    raw_next = request.GET.get("next")
    next_url: str
    if raw_next:
        decoded_next = unquote(raw_next)
        if decoded_next.startswith("http://") or decoded_next.startswith("https://"):
            next_url = decoded_next
        else:
            # Treat as path, always send the user back to the frontend domain.
            if not decoded_next.startswith("/"):
                decoded_next = "/" + decoded_next
            next_url = frontend_base + decoded_next
    else:
        # Default after Google login
        next_url = frontend_base + "/app"

    request.session["oauth_state"] = state
    request.session["oauth_next"] = next_url

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": settings.GOOGLE_OAUTH_SCOPE,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "state": state,
        "prompt": "consent",
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return redirect(auth_url)


def google_callback(request: HttpRequest) -> HttpResponse:
    stored_state = request.session.get("oauth_state")
    frontend_base = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    session_next = request.session.get("oauth_next")
    if session_next:
        decoded_next = unquote(str(session_next))
        if decoded_next.startswith("http://") or decoded_next.startswith("https://"):
            next_url = decoded_next
        else:
            if not decoded_next.startswith("/"):
                decoded_next = "/" + decoded_next
            next_url = frontend_base + decoded_next
    else:
        next_url = frontend_base + "/app"

    incoming_state = request.GET.get("state")
    if not stored_state or not incoming_state or stored_state != incoming_state:
        return HttpResponseBadRequest("Invalid OAuth state")

    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing authorization code")

    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        timeout=10,
    )
    if token_resp.status_code != 200:
        return HttpResponseBadRequest("Failed to exchange code for token")

    token_json = token_resp.json()
    access_token = token_json.get("access_token")
    if not access_token:
        return HttpResponseBadRequest("No access token received")

    userinfo_resp = requests.get(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if userinfo_resp.status_code != 200:
        return HttpResponseBadRequest("Failed to fetch user info")

    profile = userinfo_resp.json()
    email = profile.get("email")
    name = profile.get("name", "") or ""

    if not email:
        return HttpResponseBadRequest("Email is required from Google")

    first_name = profile.get("given_name") or ""
    last_name = profile.get("family_name") or ""

    user, _ = User.objects.get_or_create(
        username=email,
        defaults={
            "email": email,
            "first_name": first_name or name,
            "last_name": last_name,
        },
    )

    if user.email != email:
        user.email = email
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.save(update_fields=["email", "first_name", "last_name"])

    login(request, user)

    return redirect(next_url)


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def gsc_status(request: HttpRequest) -> Response:
    """
    Return whether the current user has a Google Search Console connection.
    """
    connected = GoogleSearchConsoleConnection.objects.filter(user=request.user).exists()
    return Response({"connected": connected})


def gsc_connect_start(request: HttpRequest) -> HttpResponse:
    """
    Start Google OAuth flow for Search Console read-only access.
    """
    if not request.user.is_authenticated:
        # Rely on frontend middleware to enforce auth, but guard anyway.
        return redirect(settings.FRONTEND_BASE_URL + "/login")

    state = secrets.token_urlsafe(32)
    request.session["gsc_state"] = state
    next_url = request.GET.get("next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"
    request.session["gsc_next"] = next_url

    redirect_uri = request.build_absolute_uri("/integrations/google-search-console/callback/")
    scope = "https://www.googleapis.com/auth/webmasters.readonly"

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "state": state,
        "prompt": "consent",
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return redirect(auth_url)


def gsc_connect_callback(request: HttpRequest) -> HttpResponse:
    """
    Handle the Google OAuth callback for Search Console access and persist tokens.
    """
    state = request.GET.get("state")
    stored_state = request.session.get("gsc_state")
    next_url = request.session.get("gsc_next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"

    if not stored_state or state != stored_state:
        return HttpResponseBadRequest("Invalid OAuth state")

    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing authorization code")

    redirect_uri = request.build_absolute_uri("/integrations/google-search-console/callback/")

    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        timeout=10,
    )
    if token_resp.status_code != 200:
        return HttpResponseBadRequest("Failed to exchange code for token")

    token_json = token_resp.json()
    access_token = token_json.get("access_token", "")
    refresh_token = token_json.get("refresh_token", "")
    token_type = token_json.get("token_type", "")
    expires_in = token_json.get("expires_in")

    expires_at: datetime | None = None
    if isinstance(expires_in, int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    if not request.user.is_authenticated:
        # User should already be authenticated via Google SSO.
        return redirect(settings.FRONTEND_BASE_URL + "/login")

    conn, _created = GoogleSearchConsoleConnection.objects.get_or_create(user=request.user)
    conn.access_token = access_token
    if refresh_token:
        conn.refresh_token = refresh_token
    conn.token_type = token_type
    conn.expires_at = expires_at
    conn.save()

    # Clean up session keys
    request.session.pop("gsc_state", None)
    request.session.pop("gsc_next", None)

    return redirect(next_url)


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def gbp_status(request: HttpRequest) -> Response:
    """
    Return whether the current user has a Google Business Profile connection.
    """
    connected = GoogleBusinessProfileConnection.objects.filter(
        user=request.user,
    ).exclude(refresh_token="").exists()
    return Response({"connected": bool(connected)})


def gbp_connect_start(request: HttpRequest) -> HttpResponse:
    """
    Start Google OAuth flow for Google Business Profile (reviews, locations).
    """
    if not request.user.is_authenticated:
        return redirect(settings.FRONTEND_BASE_URL + "/login")

    state = secrets.token_urlsafe(32)
    request.session["gbp_state"] = state
    next_url = request.GET.get("next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"
    request.session["gbp_next"] = next_url

    redirect_uri = request.build_absolute_uri("/integrations/google-business-profile/callback/")
    scope = "https://www.googleapis.com/auth/business.manage"

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "state": state,
        "prompt": "consent",
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return redirect(auth_url)


def gbp_connect_callback(request: HttpRequest) -> HttpResponse:
    """
    Handle the Google OAuth callback for Google Business Profile and persist tokens.
    """
    state = request.GET.get("state")
    stored_state = request.session.get("gbp_state")
    next_url = request.session.get("gbp_next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"

    if not stored_state or state != stored_state:
        return HttpResponseBadRequest("Invalid OAuth state")

    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing authorization code")

    redirect_uri = request.build_absolute_uri("/integrations/google-business-profile/callback/")

    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        timeout=10,
    )
    if token_resp.status_code != 200:
        return HttpResponseBadRequest("Failed to exchange code for token")

    token_json = token_resp.json()
    access_token = token_json.get("access_token", "")
    refresh_token = token_json.get("refresh_token", "")
    token_type = token_json.get("token_type", "")
    expires_in = token_json.get("expires_in")

    expires_at = None
    if isinstance(expires_in, int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    if not request.user.is_authenticated:
        return redirect(settings.FRONTEND_BASE_URL + "/login")

    conn, _created = GoogleBusinessProfileConnection.objects.get_or_create(user=request.user)
    conn.access_token = access_token
    if refresh_token:
        conn.refresh_token = refresh_token
    conn.token_type = token_type
    conn.expires_at = expires_at
    conn.save()

    request.session.pop("gbp_state", None)
    request.session.pop("gbp_next", None)
    return redirect(next_url)


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def ads_status(request: HttpRequest) -> Response:
    """
    Return whether the current user has a Google Ads connection.
    """
    from .models import GoogleAdsConnection

    connected = GoogleAdsConnection.objects.filter(
        user=request.user,
        refresh_token__isnull=False,
        customer_id__isnull=False,
    ).exclude(refresh_token="").exclude(customer_id="").exists()
    return Response({"connected": connected})


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def meta_ads_status(request: HttpRequest) -> Response:
    """
    Return whether the current user has a Meta Ads connection.

    The underlying lookup lives in ``meta_ads_utils.get_meta_ads_status_for_user``
    so that the storage / API details can evolve independently of this view.
    """

    status = get_meta_ads_status_for_user(request.user.id)
    return Response({"connected": bool(status.connected)})


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def tiktok_ads_status(request: HttpRequest) -> Response:
    """
    Return whether the current user has a TikTok Ads connection.

    The underlying lookup lives in ``tiktok_ads_utils.get_tiktok_ads_status_for_user``
    so that implementation details are kept out of the HTTP layer.
    """

    status = get_tiktok_ads_status_for_user(request.user.id)
    return Response({"connected": bool(status.connected)})


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def agent_activity_feed(request: HttpRequest) -> Response:
    """
    Return the current user's agent activity log for the dashboard "What your agents did today".
    Only returns records from the last 30 days (same window as cleanup).
    """
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=30)
    logs = (
        AgentActivityLog.objects.filter(user=request.user, created_at__gte=cutoff)
        .order_by("-created_at")[:100]
    )
    return Response({
        "activities": [
            {
                "id": log.id,
                "agent": log.agent,
                "description": log.description,
                "account_name": log.account_name or "",
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    })


def meta_ads_connect_start(request: HttpRequest) -> HttpResponse:
    """
    Start Meta Ads OAuth flow. Redirects to next URL until Meta OAuth is configured.
    When META_APP_ID etc. are set, redirect to Meta login and use meta_ads_connect_callback.
    """
    if not request.user.is_authenticated:
        return redirect(settings.FRONTEND_BASE_URL + "/login")
    next_url = request.GET.get("next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"
    # TODO: when Meta OAuth is configured, redirect to Meta and set session state/callback
    return redirect(next_url)


def meta_ads_connect_callback(request: HttpRequest) -> HttpResponse:
    """
    Handle Meta OAuth callback. Redirects to next URL until Meta OAuth is implemented.
    """
    next_url = request.session.get("meta_ads_next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"
    request.session.pop("meta_ads_state", None)
    request.session.pop("meta_ads_next", None)
    return redirect(next_url)


def tiktok_ads_connect_start(request: HttpRequest) -> HttpResponse:
    """
    Start TikTok Ads OAuth flow. Redirects to next URL until TikTok OAuth is configured.
    """
    if not request.user.is_authenticated:
        return redirect(settings.FRONTEND_BASE_URL + "/login")
    next_url = request.GET.get("next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"
    # TODO: when TikTok OAuth is configured, redirect to TikTok and set session state/callback
    return redirect(next_url)


def tiktok_ads_connect_callback(request: HttpRequest) -> HttpResponse:
    """
    Handle TikTok OAuth callback. Redirects to next URL until TikTok OAuth is implemented.
    """
    next_url = request.session.get("tiktok_ads_next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"
    request.session.pop("tiktok_ads_state", None)
    request.session.pop("tiktok_ads_next", None)
    return redirect(next_url)


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def ads_metrics(request: HttpRequest) -> Response:
    """
    Return Google Ads performance metrics for the current user.
    Uses a 1-hour cache: if we have fresh cached metrics, return them without calling the Google Ads API.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - THIRD_PARTY_CACHE_TTL
    force_refresh = request.GET.get("refresh") == "1"

    if not force_refresh:
        try:
            cache = GoogleAdsMetricsCache.objects.get(user=request.user)
            if cache.fetched_at >= cutoff:
                return Response({
                    "new_customers_this_month": cache.new_customers_this_month,
                    "new_customers_previous_month": cache.new_customers_previous_month,
                    "avg_roas": cache.avg_roas,
                    "google_search_roas": cache.google_search_roas,
                    "cost_per_customer": cache.cost_per_customer,
                    "cost_per_customer_previous": cache.cost_per_customer_previous,
                    "active_campaigns_count": cache.active_campaigns_count,
                })
        except GoogleAdsMetricsCache.DoesNotExist:
            pass

    metrics, reason, detail = fetch_ads_metrics_for_user_result(request.user.id)
    if metrics is None:
        return Response(
            {
                "error": detail or "Google Ads not connected or metrics unavailable",
                "reason": reason or "not_connected",
            },
            status=404,
        )

    cache, _ = GoogleAdsMetricsCache.objects.update_or_create(
        user=request.user,
        defaults={
            "new_customers_this_month": metrics.new_customers_this_month,
            "new_customers_previous_month": metrics.new_customers_previous_month,
            "avg_roas": metrics.avg_roas,
            "google_search_roas": metrics.google_search_roas,
            "cost_per_customer": metrics.cost_per_customer,
            "cost_per_customer_previous": metrics.cost_per_customer_previous,
            "active_campaigns_count": metrics.active_campaigns_count,
        },
    )
    return Response({
        "new_customers_this_month": cache.new_customers_this_month,
        "new_customers_previous_month": cache.new_customers_previous_month,
        "avg_roas": cache.avg_roas,
        "google_search_roas": cache.google_search_roas,
        "cost_per_customer": cache.cost_per_customer,
        "cost_per_customer_previous": cache.cost_per_customer_previous,
        "active_campaigns_count": cache.active_campaigns_count,
    })


def ads_connect_start(request: HttpRequest) -> HttpResponse:
    """
    Start Google OAuth flow for Google Ads API access.
    """
    if not request.user.is_authenticated:
        return redirect(settings.FRONTEND_BASE_URL + "/login")

    state = secrets.token_urlsafe(32)
    request.session["gads_state"] = state
    next_url = request.GET.get("next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"
    request.session["gads_next"] = next_url

    redirect_uri = request.build_absolute_uri("/integrations/google-ads/callback/")
    scope = "https://www.googleapis.com/auth/adwords"

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "state": state,
        "prompt": "consent",
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return redirect(auth_url)


def ads_connect_callback(request: HttpRequest) -> HttpResponse:
    """
    Handle the Google OAuth callback for Google Ads access and persist tokens.
    """
    from .models import GoogleAdsConnection

    state = request.GET.get("state")
    stored_state = request.session.get("gads_state")
    next_url = request.session.get("gads_next") or settings.FRONTEND_BASE_URL + "/app?tab=integrations"

    if not stored_state or state != stored_state:
        return HttpResponseBadRequest("Invalid OAuth state")

    code = request.GET.get("code")
    if not code:
        return HttpResponseBadRequest("Missing authorization code")

    redirect_uri = request.build_absolute_uri("/integrations/google-ads/callback/")

    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        timeout=10,
    )
    if token_resp.status_code != 200:
        return HttpResponseBadRequest("Failed to exchange code for token")

    token_json = token_resp.json()
    access_token = token_json.get("access_token", "")
    refresh_token = token_json.get("refresh_token", "")
    token_type = token_json.get("token_type", "")
    expires_in = token_json.get("expires_in")

    expires_at: datetime | None = None
    if isinstance(expires_in, int):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    if not request.user.is_authenticated:
        return redirect(settings.FRONTEND_BASE_URL + "/login")

    conn, _created = GoogleAdsConnection.objects.get_or_create(user=request.user)
    conn.access_token = access_token
    # Keep refresh token from user auth only; never overwrite with empty (Google often
    # omits refresh_token on re-auth, so preserve the existing one).
    if refresh_token:
        conn.refresh_token = refresh_token
    conn.token_type = token_type
    conn.expires_at = expires_at
    conn.save()

    # Try to determine the user's Ads customer ID using the newly created connection.
    connection_ok = True
    connection_error_reason = None
    connection_error_detail = None
    try:
        from google.ads.googleads.client import GoogleAdsClient  # type: ignore[import]

        if conn.refresh_token:
            ads_config = {
                "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "refresh_token": conn.refresh_token,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "use_proto_plus": True,
            }
            ads_client = GoogleAdsClient.load_from_dict(ads_config)
            customer_service = ads_client.get_service("CustomerService")
            accessible = customer_service.list_accessible_customers()
            if accessible.resource_names:
                resource_name = accessible.resource_names[0]
                customer_id = resource_name.split("/")[-1]
                conn.customer_id = customer_id
                conn.save(update_fields=["customer_id"])
            else:
                connection_ok = False
                connection_error_reason = "no_accounts"
                connection_error_detail = (
                    "No Google Ads accounts were found for this login. "
                    "Create or get access to a Google Ads account at ads.google.com, then try connecting again."
                )
        else:
            connection_ok = False
            connection_error_reason = "missing_refresh_token"
            connection_error_detail = (
                "Google did not return a refresh token. Try disconnecting and connecting again, "
                "and make sure to approve all requested permissions."
            )
    except Exception as e:
        logger.exception("[Google Ads] list_accessible_customers failed: %s", e)
        connection_ok = False
        connection_error_reason = "api_error"
        connection_error_detail = (
            f"We couldn't load your Google Ads account: {str(e)}. "
            "Check that your Google account has access to Google Ads and try reconnecting."
        )

    request.session.pop("gads_state", None)
    request.session.pop("gads_next", None)

    if not connection_ok and connection_error_reason and connection_error_detail:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        parsed = urlparse(next_url)
        params = parse_qs(parsed.query)
        params["google_ads_error"] = [connection_error_reason]
        params["google_ads_error_detail"] = [connection_error_detail]
        new_query = urlencode(params, doseq=True)
        next_url = urlunparse(parsed._replace(query=new_query))

    return redirect(next_url)


def _get_gsc_access_token(user: User) -> str | None:
    """
    Return a fresh access token for the user's Google Search Console connection,
    refreshing it with the stored refresh token if needed.
    """
    try:
        conn = GoogleSearchConsoleConnection.objects.get(user=user)
    except GoogleSearchConsoleConnection.DoesNotExist:
        return None

    # If token is still valid (with small safety window), reuse it.
    now = datetime.now(timezone.utc)
    if conn.expires_at and conn.expires_at > now + timedelta(seconds=60) and conn.access_token:
        return conn.access_token

    if not conn.refresh_token:
        return conn.access_token or None

    token_data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": conn.refresh_token,
        "grant_type": "refresh_token",
    }
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        timeout=10,
    )
    if resp.status_code != 200:
        return conn.access_token or None

    data = resp.json()
    access_token = data.get("access_token")
    expires_in = data.get("expires_in")
    if not access_token:
        return conn.access_token or None

    conn.access_token = access_token
    if isinstance(expires_in, int):
        conn.expires_at = now + timedelta(seconds=expires_in)
    conn.save(update_fields=["access_token", "expires_at"])
    return access_token


def _gsc_query(
    access_token: str,
    site_url: str,
    start: date,
    end: date,
) -> list[dict]:
    """
    Call the Search Console searchAnalytics.query endpoint for the given site and date range.
    """
    endpoint = (
        "https://searchconsole.googleapis.com/webmasters/v3/sites/"
        f"{quote(site_url, safe='')}/searchAnalytics/query"
    )
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": ["query"],
        "rowLimit": 25000,
    }
    resp = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        json=body,
        timeout=20,
    )
    if resp.status_code != 200:
        return []
    data = resp.json()
    return data.get("rows", []) or []


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def seo_overview(request: HttpRequest) -> Response:
    """
    Return SEO overview metrics for the dashboard, powered by Google Search Console.
    Uses a 1-hour cache: if we have fresh snapshot data, return it without calling GSC API.
    """
    today = datetime.now(timezone.utc).date()
    start_current = today.replace(day=1)
    now = datetime.now(timezone.utc)
    cutoff = now - THIRD_PARTY_CACHE_TTL
    force_refresh = request.GET.get("refresh") == "1"

    # Serve from cache if we have a snapshot for this period fetched within the last hour (unless refresh=1).
    if not force_refresh:
        try:
            snapshot = SEOOverviewSnapshot.objects.get(
                user=request.user,
                period_start=start_current,
            )
            if snapshot.last_fetched_at >= cutoff:
                prev_clicks = snapshot.prev_organic_visitors or 0
                organic_visitors = snapshot.organic_visitors or 0
                if prev_clicks == 0:
                    organic_growth_pct = 100.0 if organic_visitors > 0 else 0.0
                else:
                    organic_growth_pct = ((organic_visitors - prev_clicks) / prev_clicks) * 100.0
                return Response(
                    {
                        "organic_visitors": organic_visitors,
                        "keywords_ranking": snapshot.keywords_ranking or 0,
                        "top3_positions": snapshot.top3_positions or 0,
                        "organic_growth_pct": organic_growth_pct,
                    },
                )
        except SEOOverviewSnapshot.DoesNotExist:
            pass

    # Cache miss, stale, or refresh=1: call Google Search Console API.
    profile = BusinessProfile.objects.filter(user=request.user).first()
    site_url = (profile.website_url if profile else None) or getattr(
        settings,
        "GOOGLE_SITE_URL",
        "",
    )
    if not site_url:
        return Response(
            {"detail": "No site URL configured for Search Console."},
            status=400,
        )

    access_token = _get_gsc_access_token(request.user)
    if not access_token:
        return Response(
            {"detail": "Google Search Console is not connected."},
            status=400,
        )

    if start_current.month == 1:
        prev_year = start_current.year - 1
        prev_month = 12
    else:
        prev_year = start_current.year
        prev_month = start_current.month - 1
    start_prev = date(prev_year, prev_month, 1)
    end_prev = start_current - timedelta(days=1)

    rows_current = _gsc_query(access_token, site_url, start_current, today)
    rows_prev = _gsc_query(access_token, site_url, start_prev, end_prev)

    organic_visitors = int(sum(float(r.get("clicks", 0)) for r in rows_current))
    keywords_ranking = len(rows_current)
    top3_positions = sum(1 for r in rows_current if float(r.get("position", 9999)) <= 3.0)

    prev_clicks = int(sum(float(r.get("clicks", 0)) for r in rows_prev))
    if prev_clicks == 0:
        organic_growth_pct = 100.0 if organic_visitors > 0 else 0.0
    else:
        organic_growth_pct = ((organic_visitors - prev_clicks) / prev_clicks) * 100.0

    snapshot, _ = SEOOverviewSnapshot.objects.get_or_create(
        user=request.user,
        period_start=start_current,
    )
    snapshot.organic_visitors = organic_visitors
    snapshot.prev_organic_visitors = prev_clicks
    snapshot.keywords_ranking = keywords_ranking
    snapshot.top3_positions = top3_positions
    snapshot.save()

    return Response(
        {
            "organic_visitors": organic_visitors,
            "keywords_ranking": keywords_ranking,
            "top3_positions": top3_positions,
            "organic_growth_pct": organic_growth_pct,
        },
    )


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def seo_keywords(request: HttpRequest) -> Response:
    """
    Return a unified High-Intent Keywords dataset combining:

    - Google Search Console: query, clicks, impressions, ctr, position
    - Google Ads KeywordPlanIdeaService: avg_monthly_searches, competition, competition_index, bid range
    - Rule-based intent classification (HIGH / MEDIUM / LOW)
    """
    profile = BusinessProfile.objects.filter(user=request.user).first()
    site_url = (profile.website_url if profile else None) or getattr(
        settings,
        "GOOGLE_SITE_URL",
        "",
    )

    today = datetime.now(timezone.utc).date()

    # If GSC is connected, use it to get per-site ranking & position deltas.
    access_token = _get_gsc_access_token(request.user)
    results: list[dict] = []

    logger.info(
        "[SEO keywords] user_id=%s, site_url=%s, has_gsc_token=%s",
        request.user.id,
        site_url or "(none)",
        bool(access_token),
    )

    if site_url and access_token:
        # Current period: last 30 days
        start = today - timedelta(days=30)
        prev_start = start - timedelta(days=30)
        prev_end = start - timedelta(days=1)

        rows_current = _gsc_query(access_token, site_url, start, today)
        rows_prev = _gsc_query(access_token, site_url, prev_start, prev_end)

        # Index previous-period positions by query for quick lookup
        prev_positions: dict[str, float] = {}
        for row in rows_prev:
            keys = row.get("keys") or []
            if not keys:
                continue
            q = keys[0]
            prev_positions[q] = float(row.get("position", 0))

        # Sort by clicks descending and take top N.
        sorted_rows = sorted(
            rows_current,
            key=lambda r: float(r.get("clicks", 0)),
            reverse=True,
        )
        top_rows = sorted_rows[:50]

        keywords = [r["keys"][0] for r in top_rows if r.get("keys")]

        # Fetch Ads ideas with caching, using business context (industry / description)
        # to improve suggestions.
        industry = profile.industry if profile and profile.industry else None
        description = profile.description if profile and profile.description else None

        ads_ideas = {}
        try:
            logger.info("[SEO keywords] GSC branch: calling fetch_keyword_ideas_for_user with %s keywords.", len(keywords))
            ads_ideas = fetch_keyword_ideas_for_user(
                request.user.id,
                keywords,
                industry=industry,
                description=description,
            )
            logger.info("[SEO keywords] GSC branch: got %s ads_ideas.", len(ads_ideas))
        except Exception as e:
            logger.exception(
                "[SEO keywords] GSC branch: fetch_keyword_ideas_for_user failed: %s. Using GSC-only data.",
                e,
            )
            ads_ideas = {}

        for row in top_rows:
            query_keys = row.get("keys") or []
            if not query_keys:
                continue
            query = query_keys[0]

            ads = ads_ideas.get(query)

            clicks = float(row.get("clicks", 0))
            impressions = float(row.get("impressions", 0))
            ctr = float(row.get("ctr", 0))
            position = float(row.get("position", 0))

            prev_pos = prev_positions.get(query)
            # Positive delta means improvement (moved up).
            position_change = None
            if prev_pos is not None:
                position_change = prev_pos - position

            results.append(
                {
                    "keyword": query,
                    "avg_monthly_searches": (
                        int(ads.avg_monthly_searches)
                        if ads and ads.avg_monthly_searches is not None
                        else None
                    ),
                    "intent": classify_intent(query),
                    "current_position": position,
                    "position_change": position_change,
                    "impressions": int(impressions),
                    "clicks": int(clicks),
                    "ctr": ctr,
                },
            )

    else:
        # No GSC connection: use user's Google Ads connection to get
        # Keyword Planner recommendations from business profile seeds.
        logger.info("[SEO keywords] No-GSC branch: using Keyword Planner with profile seeds only.")
        industry = profile.industry if profile and profile.industry else None
        description = profile.description if profile and profile.description else None
        if not industry and not description:
            description = "services"  # fallback seed so API returns recommendations
            logger.info("[SEO keywords] No-GSC branch: no industry/description, using fallback seed 'services'.")
        ads_ideas = {}
        try:
            ads_ideas = fetch_keyword_ideas_for_user(
                request.user.id,
                [],  # no seed keywords; use industry/description only
                industry=industry,
                description=description,
            )
            logger.info("[SEO keywords] No-GSC branch: got %s ads_ideas.", len(ads_ideas))
        except Exception as e:
            logger.exception(
                "[SEO keywords] No-GSC branch: fetch_keyword_ideas_for_user failed: %s. Returning empty keywords.",
                e,
            )
            ads_ideas = {}

        # Build list from recommendations; add intent and impact (competition, bid range).
        idea_list = list(ads_ideas.values())
        # Sort by intent (HIGH first) then by avg_monthly_searches descending.
        def sort_key(idea):
            intent = classify_intent(idea.keyword)
            order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            return (order.get(intent, 1), -(idea.avg_monthly_searches or 0))

        idea_list.sort(key=sort_key)
        for idea in idea_list[:50]:
            results.append(
                {
                    "keyword": idea.keyword,
                    "avg_monthly_searches": idea.avg_monthly_searches,
                    "competition": idea.competition,
                    "competition_index": idea.competition_index,
                    "low_top_of_page_bid_micros": idea.low_top_of_page_bid_micros,
                    "high_top_of_page_bid_micros": idea.high_top_of_page_bid_micros,
                    "intent": classify_intent(idea.keyword),
                    "current_position": None,
                    "position_change": None,
                    "impressions": 0,
                    "clicks": 0,
                    "ctr": 0.0,
                },
            )

    logger.info("[SEO keywords] Returning %s keywords for user_id=%s.", len(results), request.user.id)
    return Response({"keywords": results})


def _reviews_overview_response_from_snapshot(snapshot: ReviewsOverviewSnapshot) -> Response:
    """Build the same JSON shape as fetch_gbp_overview for consistency."""
    return Response({
        "star_rating": float(snapshot.star_rating or 0),
        "previous_star_rating": float(snapshot.previous_star_rating or 0),
        "total_reviews": snapshot.total_reviews or 0,
        "new_reviews_this_month": snapshot.new_reviews_this_month or 0,
        "response_rate_pct": float(snapshot.response_rate_pct or 0),
        "industry_avg_response_pct": float(snapshot.industry_avg_response_pct or 45),
        "requests_sent": snapshot.requests_sent or 0,
        "conversion_pct": float(snapshot.conversion_pct or 0),
    })


@csrf_exempt
@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def reviews_overview(request: HttpRequest) -> Response:
    """
    Return Reviews Agent overview: star rating, total reviews, response rate, requests sent.
    Uses a 1-hour cache: if we have fresh GBP snapshot data, return it without calling the API.
    """
    from .gbp_client import fetch_gbp_overview

    connected = GoogleBusinessProfileConnection.objects.filter(user=request.user).exclude(
        refresh_token=""
    ).exists()

    if connected:
        now = datetime.now(timezone.utc)
        cutoff = now - THIRD_PARTY_CACHE_TTL
        force_refresh = request.GET.get("refresh") == "1"
        if not force_refresh:
            try:
                snapshot = ReviewsOverviewSnapshot.objects.get(user=request.user)
                if snapshot.last_fetched_at >= cutoff:
                    return _reviews_overview_response_from_snapshot(snapshot)
            except ReviewsOverviewSnapshot.DoesNotExist:
                pass

        try:
            data = fetch_gbp_overview(request.user)
            if data:
                return Response(data)
        except Exception as e:
            logger.exception("[reviews_overview] fetch_gbp_overview failed: %s", e)

    # Fallback: cached snapshot or defaults
    try:
        snapshot = ReviewsOverviewSnapshot.objects.get(user=request.user)
        return _reviews_overview_response_from_snapshot(snapshot)
    except ReviewsOverviewSnapshot.DoesNotExist:
        return Response({
            "star_rating": 0,
            "previous_star_rating": 0,
            "total_reviews": 0,
            "new_reviews_this_month": 0,
            "response_rate_pct": 0,
            "industry_avg_response_pct": 45,
            "requests_sent": 0,
            "conversion_pct": 0,
            "connected": False,
        })


@csrf_exempt
@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def seo_chat(request: HttpRequest) -> Response:
    """SEO agent chat endpoint – delegates to OpenAI utils implementation."""
    return openai_utils.seo_chat(request)


@csrf_exempt
@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def reviews_chat(request: HttpRequest) -> Response:
    """Reviews agent chat endpoint – same pattern as SEO, different system role and tables."""
    return openai_utils.reviews_chat(request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request: HttpRequest) -> JsonResponse:
    user = request.user
    return JsonResponse(
        {
            "id": user.id,
            "email": user.email,
            "first_name": getattr(user, "first_name", ""),
            "last_name": getattr(user, "last_name", ""),
        }
    )


@csrf_exempt
@api_view(["GET", "PATCH", "PUT"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def business_profile(request: HttpRequest) -> Response:
    """
    Retrieve or upsert the authenticated user's business profile.

    - GET: returns the current profile (creates an empty one if missing).
    - PATCH/PUT: updates existing profile fields; creates a profile if it does not exist yet.
    """
    profile, _created = BusinessProfile.objects.get_or_create(user=request.user)

    if request.method == "GET":
        serializer = BusinessProfileSerializer(profile)
        return Response(serializer.data)

    # For PATCH/PUT, apply partial updates
    serializer = BusinessProfileSerializer(
        profile,
        data=request.data,
        partial=True,
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@csrf_exempt
@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def api_logout(request: HttpRequest) -> Response:
    """
    Log out the current user from the Django session (Google SSO).
    """
    django_logout(request)
    return Response({"success": True})

