"""
Reconcile AEOPromptExecutionAggregate btree index names with 0068 / 0069.

Replaces a failing ``RenameIndex`` pair (0048 long names -> short canonical names):
after ``0068_aeopromptexecutionaggregate_index_names`` the short indexes may already
exist while legacy long-named indexes remain, so ``RenameIndex`` hits
"relation already exists".

PostgreSQL-only, idempotent:
- Both canonical and legacy: ``DROP INDEX`` legacy after verifying non-unique btree
  on ``accounts_aeopromptexecutionaggregate`` with expected columns (not the unique
  constraint ``accounts_aeo_prompt_agg_profile_run_hash_uq``).
- Only legacy: ``ALTER INDEX ... RENAME TO`` canonical.
- Only canonical: no-op.
"""

from django.db import migrations


STATUS_CANONICAL = "acct_aeoagg_runstat_idx"
HASH_CANONICAL = "acct_aeoagg_prhash_idx"
LEGACY_STATUS = "accounts_aeo_prompt_agg_profile_run_status_idx"
LEGACY_HASH = "accounts_aeo_prompt_agg_profile_hash_idx"
TABLE = "accounts_aeopromptexecutionaggregate"


def _index_exists(cursor, name: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relkind = 'i'
          AND c.relname = %s
        """,
        [name],
    )
    return cursor.fetchone() is not None


def _index_meta(cursor, index_name: str):
    cursor.execute(
        """
        SELECT i.indisunique, pg_get_indexdef(i.indexrelid)
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_class t ON t.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = current_schema()
          AND t.relname = %s
          AND c.relname = %s
        """,
        [TABLE, index_name],
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {"unique": bool(row[0]), "def": str(row[1] or "")}


def _def_matches(defn: str, required: list[str], forbidden: list[str]) -> bool:
    d = defn.lower()
    return all(x.lower() in d for x in required) and not any(x.lower() in d for x in forbidden)


def _reconcile_pair(cursor, qn, legacy: str, canonical: str, required: list[str], forbidden: list[str]) -> None:
    has_canonical = _index_exists(cursor, canonical)
    has_legacy = _index_exists(cursor, legacy)
    if has_canonical and has_legacy:
        meta = _index_meta(cursor, legacy)
        if not meta or meta["unique"]:
            return
        if not _def_matches(meta["def"], required, forbidden):
            return
        cursor.execute("DROP INDEX {}".format(qn(legacy)))
        return
    if has_legacy and not has_canonical:
        meta = _index_meta(cursor, legacy)
        if not meta or meta["unique"]:
            return
        if not _def_matches(meta["def"], required, forbidden):
            return
        cursor.execute(
            "ALTER INDEX {} RENAME TO {}".format(qn(legacy), qn(canonical)),
        )


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    qn = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        _reconcile_pair(
            cursor,
            qn,
            LEGACY_STATUS,
            STATUS_CANONICAL,
            required=["profile_id", "execution_run_id", "stability_status"],
            forbidden=["prompt_hash"],
        )
        _reconcile_pair(
            cursor,
            qn,
            LEGACY_HASH,
            HASH_CANONICAL,
            required=["profile_id", "prompt_hash"],
            forbidden=["execution_run_id", "stability_status"],
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0074_seooverviewsnapshot_structured_issues"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
