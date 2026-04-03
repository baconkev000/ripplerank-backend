import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0040_aeoresponsesnapshot_execution_link"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnboardingOnPageCrawl",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("max_pages", models.PositiveSmallIntegerField(default=10)),
                ("pages", models.JSONField(blank=True, default=list)),
                ("task_id", models.CharField(blank=True, default="", max_length=128)),
                ("exit_reason", models.CharField(blank=True, default="", max_length=64)),
                ("error_message", models.TextField(blank=True, default="")),
                (
                    "context",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Optional business_name, location for mention detection.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business_profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="onboarding_onpage_crawls",
                        to="accounts.businessprofile",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="onboarding_onpage_crawls",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Onboarding on-page crawl",
                "verbose_name_plural": "Onboarding on-page crawls",
                "ordering": ("-created_at",),
            },
        ),
    ]
