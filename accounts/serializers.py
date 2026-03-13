from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import BusinessProfile


User = get_user_model()

class BusinessProfileSerializer(serializers.ModelSerializer):
    website_url = serializers.CharField(
        required=False,
        allow_blank=True
    )
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = BusinessProfile
        fields = [
            "id",
            "email",
            "full_name",
            "business_name",
            "business_address",
            "industry",
            "tone_of_voice",
            "phone",
            "description",
            "website_url",
            "plan",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "email", "created_at", "updated_at"]

    def validate_website_url(self, value):
        """Normalize URL to include scheme."""
        if value:
            value = value.strip()
            if not value.startswith(("http://", "https://")):
                value = "https://" + value
        return value
