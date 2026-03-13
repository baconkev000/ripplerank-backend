from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_businessprofile_plan"),
    ]

    operations = [
        migrations.CreateModel(
            name="OnPageAuditSnapshot",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(max_length=255)),
                ("last_fetched_at", models.DateTimeField(auto_now=True)),
                ("pages_missing_titles", models.IntegerField(default=0)),
                ("pages_missing_descriptions", models.IntegerField(default=0)),
                ("pages_bad_h1", models.IntegerField(default=0)),
                ("images_missing_alt", models.IntegerField(default=0)),
                ("broken_internal_links", models.IntegerField(default=0)),
                ("error_pages_4xx_5xx", models.IntegerField(default=0)),
                ("pages_missing_canonical", models.IntegerField(default=0)),
                ("duplicate_canonical_targets", models.IntegerField(default=0)),
                ("has_robots_txt", models.BooleanField(default=False)),
                ("has_sitemap_xml", models.BooleanField(default=False)),
                ("metadata_score", models.IntegerField(default=0)),
                ("content_structure_score", models.IntegerField(default=0)),
                ("accessibility_score", models.IntegerField(default=0)),
                ("internal_link_score", models.IntegerField(default=0)),
                ("indexability_score", models.IntegerField(default=0)),
                ("onpage_seo_score", models.IntegerField(default=0)),
                ("technical_seo_score", models.IntegerField(default=0)),
                ("issue_summaries", models.JSONField(blank=True, default=dict)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="onpage_audit_snapshots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "On-page audit snapshot",
                "verbose_name_plural": "On-page audit snapshots",
                "unique_together": {("user", "domain")},
            },
        ),
    ]

