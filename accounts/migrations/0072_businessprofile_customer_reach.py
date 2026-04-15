from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0071_businessprofilemembership_hidden_from_team_ui"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessprofile",
            name="customer_reach",
            field=models.CharField(
                choices=[("online", "Online"), ("local", "Local")],
                default="online",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="businessprofile",
            name="customer_reach_city",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="businessprofile",
            name="customer_reach_state",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
