from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0063_businessprofile_aeo_prompt_expansion"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessprofile",
            name="aeo_full_phase_eta_state",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Rolling durations + recorded prompt hashes for full-phase ETA (prompt-coverage).",
            ),
        ),
    ]
