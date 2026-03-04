from django.contrib import admin

from .models import BusinessProfile, GoogleSearchConsoleConnection


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "business_name",
        "industry",
        "tone_of_voice",
        "created_at",
        "updated_at",
    )
    search_fields = ("user__email", "user__username", "business_name", "industry")
    list_filter = ("industry", "tone_of_voice", "created_at")


@admin.register(GoogleSearchConsoleConnection)
class GoogleSearchConsoleConnectionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "updated_at")
    search_fields = ("user__email", "user__username")

