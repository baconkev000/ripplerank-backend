from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0054_add_aggregate_combined_rollup_fields"),
    ]

    operations = [
        migrations.DeleteModel(
            name="GoogleAdsConnection",
        ),
        migrations.DeleteModel(
            name="GoogleAdsKeywordIdea",
        ),
        migrations.DeleteModel(
            name="GoogleBusinessProfileConnection",
        ),
        migrations.DeleteModel(
            name="GoogleSearchConsoleConnection",
        ),
        migrations.DeleteModel(
            name="MetaAdsConnection",
        ),
        migrations.DeleteModel(
            name="OnPageAuditSnapshot",
        ),
        migrations.DeleteModel(
            name="ReviewsConversation",
        ),
        migrations.DeleteModel(
            name="ReviewsMessage",
        ),
        migrations.DeleteModel(
            name="ReviewsOverviewSnapshot",
        ),
    ]
