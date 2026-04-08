from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0053_add_provider_pass_history_json"),
    ]

    operations = [
        migrations.AddField(
            model_name="aeopromptexecutionaggregate",
            name="combined_competitor_counts",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="aeopromptexecutionaggregate",
            name="combined_citation_counts",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="aeopromptexecutionaggregate",
            name="combined_provider_breakdown",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="aeopromptexecutionaggregate",
            name="combined_total_passes_observed",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="aeopromptexecutionaggregate",
            name="combined_total_unique_competitors",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="aeopromptexecutionaggregate",
            name="combined_total_unique_citations",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="aeopromptexecutionaggregate",
            name="combined_last_recomputed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

