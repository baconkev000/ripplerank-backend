# Generated manually for AEODashboardBundleCache

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0065_aeopromptexecutionaggregate_perplexity"),
    ]

    operations = [
        migrations.CreateModel(
            name="AEODashboardBundleCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "profile",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="aeo_dashboard_bundle_cache",
                        to="accounts.businessprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "AEO dashboard bundle cache",
                "verbose_name_plural": "AEO dashboard bundle caches",
            },
        ),
    ]
