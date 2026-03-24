from django.db import migrations, models


# PostgreSQL: idempotent DDL for partial applies / manual schema drift (same pattern as 0016).
ADD_COLUMNS_SQL = """
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS cached_location_mode varchar(16) NOT NULL DEFAULT 'organic';
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS cached_location_code integer NOT NULL DEFAULT 0;
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS cached_location_label varchar(255) NOT NULL DEFAULT '';
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS local_verification_applied boolean NOT NULL DEFAULT false;
ALTER TABLE accounts_seooverviewsnapshot ADD COLUMN IF NOT EXISTS local_verified_keyword_count integer NOT NULL DEFAULT 0;
"""

# Replace legacy (user, period_start) unique with mode-aware unique when needed.
UNIQUE_CONSTRAINT_SQL = """
DO $$
DECLARE
    r RECORD;
    def_text text;
    has_new_uniq boolean := false;
BEGIN
    FOR r IN
        SELECT c.conname, pg_get_constraintdef(c.oid) AS def
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        JOIN pg_namespace n ON t.relnamespace = n.oid
        WHERE n.nspname = current_schema()
          AND t.relname = 'accounts_seooverviewsnapshot'
          AND c.contype = 'u'
    LOOP
        def_text := r.def;
        IF position('cached_location_mode' in def_text) > 0 THEN
            has_new_uniq := true;
        ELSIF position('user_id' in def_text) > 0
          AND position('period_start' in def_text) > 0
          AND position('cached_location_mode' in def_text) = 0 THEN
            EXECUTE format('ALTER TABLE accounts_seooverviewsnapshot DROP CONSTRAINT %I', r.conname);
        END IF;
    END LOOP;

    IF NOT has_new_uniq THEN
        BEGIN
            ALTER TABLE accounts_seooverviewsnapshot
            ADD CONSTRAINT accounts_seooverview_snap_loc_ctx_uniq
            UNIQUE (user_id, period_start, cached_location_mode, cached_location_code);
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END;
    END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0029_businessprofile_seo_location_mode_local"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    ADD_COLUMNS_SQL + UNIQUE_CONSTRAINT_SQL,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="cached_location_mode",
                    field=models.CharField(blank=True, default="organic", max_length=16),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="cached_location_code",
                    field=models.IntegerField(default=0),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="cached_location_label",
                    field=models.CharField(blank=True, default="", max_length=255),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="local_verification_applied",
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name="seooverviewsnapshot",
                    name="local_verified_keyword_count",
                    field=models.IntegerField(default=0),
                ),
                migrations.AlterUniqueTogether(
                    name="seooverviewsnapshot",
                    unique_together={
                        ("user", "period_start", "cached_location_mode", "cached_location_code")
                    },
                ),
            ],
        ),
    ]
