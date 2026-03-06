# Generated manually for 1-hour third-party API cache

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_agentactivitylog"),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleAdsMetricsCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fetched_at", models.DateTimeField(auto_now=True)),
                ("new_customers_this_month", models.IntegerField(default=0)),
                ("new_customers_previous_month", models.IntegerField(default=0)),
                ("avg_roas", models.FloatField(default=0)),
                ("google_search_roas", models.FloatField(default=0)),
                ("cost_per_customer", models.FloatField(default=0)),
                ("cost_per_customer_previous", models.FloatField(default=0)),
                ("active_campaigns_count", models.IntegerField(default=0)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="google_ads_metrics_cache",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Google Ads metrics cache",
                "verbose_name_plural": "Google Ads metrics caches",
            },
        ),
    ]
