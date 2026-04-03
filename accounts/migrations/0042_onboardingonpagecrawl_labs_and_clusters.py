from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0041_onboardingonpagecrawl"),
    ]

    operations = [
        migrations.AddField(
            model_name="onboardingonpagecrawl",
            name="crawl_topic_seeds",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Service/topic phrases extracted from the on-page crawl only.",
            ),
        ),
        migrations.AddField(
            model_name="onboardingonpagecrawl",
            name="ranked_keywords",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Normalized ranked keyword rows from Labs (keyword, rank, volume).",
            ),
        ),
        migrations.AddField(
            model_name="onboardingonpagecrawl",
            name="ranked_keywords_error",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Set when Labs ranked_keywords call fails (crawl may still succeed).",
            ),
        ),
        migrations.AddField(
            model_name="onboardingonpagecrawl",
            name="topic_clusters",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Topic clusters: crawl seeds matched to ranked keywords.",
            ),
        ),
    ]
