from django.db import migrations, models


def forwards_normalize_plan(apps, schema_editor):
    BusinessProfile = apps.get_model("accounts", "BusinessProfile")
    for bp in BusinessProfile.objects.all().only("id", "plan"):
        raw = str(getattr(bp, "plan", None) or "").strip().lower()
        if raw in ("pro", "professional"):
            new_p = "pro"
        elif raw in ("advanced", "scale", "enterprise"):
            new_p = "advanced"
        else:
            new_p = "starter"
        if bp.plan != new_p:
            bp.plan = new_p
            bp.save(update_fields=["plan"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0055_remove_unused_integrations_and_reviews_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrackedCompetitor",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "domain",
                    models.CharField(
                        db_index=True,
                        help_text="Normalized base host (no path, no scheme, lowercase, no leading www.).",
                        max_length=253,
                        unique=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Tracked competitor",
                "verbose_name_plural": "Tracked competitors",
                "ordering": ("domain",),
            },
        ),
        migrations.RemoveField(
            model_name="businessprofile",
            name="tone_of_voice",
        ),
        migrations.RunPython(forwards_normalize_plan, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="businessprofile",
            name="plan",
            field=models.CharField(
                choices=[
                    ("starter", "Starter"),
                    ("pro", "Pro"),
                    ("advanced", "Advanced"),
                ],
                default="starter",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="businessprofile",
            name="tracked_competitors",
            field=models.ManyToManyField(
                blank=True,
                related_name="+",
                to="accounts.trackedcompetitor",
            ),
        ),
    ]
