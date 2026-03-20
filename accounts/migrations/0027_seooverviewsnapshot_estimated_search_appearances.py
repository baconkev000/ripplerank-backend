from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_aeooverviewsnapshot_recommendations_refreshed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="seooverviewsnapshot",
            name="estimated_search_appearances_monthly",
            field=models.IntegerField(default=0),
        ),
    ]
