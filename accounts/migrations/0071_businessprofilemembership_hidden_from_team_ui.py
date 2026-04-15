from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0070_aeo_custom_prompt_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessprofilemembership",
            name="hidden_from_team_ui",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When true, keep this membership for access control but hide it from "
                    "customer-facing team member lists."
                ),
            ),
        ),
    ]

