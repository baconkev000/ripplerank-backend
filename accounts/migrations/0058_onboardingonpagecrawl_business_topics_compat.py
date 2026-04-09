from django.db import migrations, models


def _ensure_business_topics_column(apps, schema_editor) -> None:
    """Add business_topics only when missing (handles DBs that predate this repo state)."""
    model = apps.get_model("accounts", "OnboardingOnPageCrawl")
    table = model._meta.db_table
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        desc = connection.introspection.get_table_description(cursor, table)
        names = {row.name for row in desc}
    if "business_topics" in names:
        return
    field = models.JSONField(default=list, blank=True)
    field.set_attributes_from_name("business_topics")
    schema_editor.add_field(model, field)


def _noop_reverse(apps, schema_editor) -> None:
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0057_onboardingonpagecrawl_review_topics"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(_ensure_business_topics_column, _noop_reverse),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="onboardingonpagecrawl",
                    name="business_topics",
                    field=models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Unused; onboarding review topics use ``review_topics``. Kept for database compatibility.",
                    ),
                ),
            ],
        ),
    ]
