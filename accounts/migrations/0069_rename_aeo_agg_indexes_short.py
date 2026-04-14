"""
Rename AEOPromptExecutionAggregate indexes to <=30-char names (Django E034).

0048 / 0068 used longer names; the model now uses ``acct_aeoagg_runstat_idx`` and
``acct_aeoagg_prhash_idx``. PostgreSQL: rename old → new when present.
"""

from django.db import migrations

NEW_STATUS = "acct_aeoagg_runstat_idx"
NEW_HASH = "acct_aeoagg_prhash_idx"
OLD_STATUS = "accounts_aeo_prompt_agg_profile_run_status_idx"
OLD_HASH = "accounts_aeo_prompt_agg_profile_hash_idx"
TABLE = "accounts_aeopromptexecutionaggregate"


def _rename_if(cursor, qn, old: str, new: str) -> None:
    cursor.execute(
        """
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relkind = 'i'
          AND c.relname = %s
        """,
        [new],
    )
    if cursor.fetchone():
        return
    cursor.execute(
        """
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relkind = 'i'
          AND c.relname = %s
        """,
        [old],
    )
    if cursor.fetchone():
        cursor.execute("ALTER INDEX {} RENAME TO {}".format(qn(old), qn(new)))


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    qn = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        _rename_if(cursor, qn, OLD_STATUS, NEW_STATUS)
        _rename_if(cursor, qn, OLD_HASH, NEW_HASH)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0068_aeopromptexecutionaggregate_index_names"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
