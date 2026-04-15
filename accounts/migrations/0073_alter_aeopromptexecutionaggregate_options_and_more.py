# Aligns AEOPromptExecutionAggregate Meta options with models.py (ordering in options only).
# Deploy recovery if 0073 was applied before 0072: remove the 0073 row from django_migrations,
# then `python manage.py migrate accounts` so 0072 runs first, then 0073.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0072_businessprofile_customer_reach"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="aeopromptexecutionaggregate",
            options={
                "ordering": ("-updated_at", "-id"),
            },
        ),
    ]
