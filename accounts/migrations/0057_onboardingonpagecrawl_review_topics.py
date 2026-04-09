from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0056_tracked_competitors_plan_tone_cleanup"),
    ]

    operations = [
        migrations.AddField(
            model_name="onboardingonpagecrawl",
            name="review_topics",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='LLM-generated business topics, e.g. [{"topic": "...", "category": "...", "rationale": "..."}].',
            ),
        ),
        migrations.AddField(
            model_name="onboardingonpagecrawl",
            name="review_topics_error",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Set when review topic generation fails or returns nothing usable.",
            ),
        ),
    ]
