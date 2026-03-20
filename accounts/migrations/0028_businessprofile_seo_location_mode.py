from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0027_seooverviewsnapshot_estimated_search_appearances"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessprofile",
            name="seo_location_mode",
            field=models.CharField(
                choices=[("organic", "Organic"), ("global", "Global")],
                default="organic",
                max_length=16,
            ),
        ),
    ]
