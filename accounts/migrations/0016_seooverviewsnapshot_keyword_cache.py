from django.db import migrations, models


# PostgreSQL: add columns only if they don't exist (idempotent for partial applies)
ADD_COLUMNS_SQL = """
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS refreshed_at TIMESTAMP WITH TIME ZONE NULL;
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS cached_domain VARCHAR(255) NOT NULL DEFAULT '';
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS top_keywords JSONB NOT NULL DEFAULT '[]';
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS total_search_volume INTEGER NOT NULL DEFAULT 0;
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS missed_searches_monthly INTEGER NOT NULL DEFAULT 0;
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS search_visibility_percent INTEGER NOT NULL DEFAULT 0;
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS search_performance_score INTEGER NULL;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_onpageauditsnapshot_pages_audited"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(ADD_COLUMNS_SQL, migrations.RunSQL.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="refreshed_at",
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="cached_domain",
                    field=models.CharField(blank=True, max_length=255),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="top_keywords",
                    field=models.JSONField(blank=True, default=list),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="total_search_volume",
                    field=models.IntegerField(default=0),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="missed_searches_monthly",
                    field=models.IntegerField(default=0),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="search_visibility_percent",
                    field=models.IntegerField(default=0),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="search_performance_score",
                    field=models.IntegerField(blank=True, null=True),
                ),
            ],
        ),
    ]
