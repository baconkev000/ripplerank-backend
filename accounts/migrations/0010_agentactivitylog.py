# Generated manually for AgentActivityLog

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_reviewsconversation_reviewsmessage"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentActivityLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("agent", models.CharField(choices=[("seo", "SEO Agent"), ("ads", "Ads Agent"), ("reviews", "Reviews Agent")], max_length=32)),
                ("description", models.TextField(help_text="What was completed")),
                ("account_name", models.CharField(blank=True, help_text="Optional: connected account/integration (e.g. Google Ads, Google Search Console)", max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agent_activity_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Agent activity log",
                "verbose_name_plural": "Agent activity logs",
            },
        ),
    ]
