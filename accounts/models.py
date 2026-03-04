from django.conf import settings
from django.db import models


class BusinessProfile(models.Model):
    """
    Stores business profile settings for a user.

    Each user has at most one BusinessProfile, linked via a foreign key
    to the Django user model (which includes the user's email).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_profile",
    )

    full_name = models.CharField(max_length=255, blank=True)
    business_name = models.CharField(max_length=255, blank=True)
    business_address = models.CharField(max_length=255, blank=True)

    # Industry is intentionally a free-text field (no choices).
    industry = models.CharField(max_length=255, blank=True)

    # Tone of voice for marketing/communications.
    tone_of_voice = models.CharField(max_length=64, blank=True)

    phone = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    website_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Business profile"
        verbose_name_plural = "Business profiles"

    def __str__(self) -> str:
        return f"BusinessProfile(user={self.user!s})"


class GoogleSearchConsoleConnection(models.Model):
    """
    Tracks whether a user has granted this app access to Google Search Console.

    Tokens are stored to enable read-only API access (webmasters.readonly scope).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gsc_connection",
    )

    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_type = models.CharField(max_length=32, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Google Search Console connection"
        verbose_name_plural = "Google Search Console connections"

    def __str__(self) -> str:
        return f"GSCConnection(user={self.user!s})"

