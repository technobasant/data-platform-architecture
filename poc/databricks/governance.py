"""Two governance questions for the data model, measured on Databricks.

  erasure-by-model  What erasing one person costs, by where the model keeps personal data.
                    The same 31.85 million events (the speed test's data, workspace.dpa_bi)
                    as UniForm tables two ways: with the user's e-mail and name copied into
                    every event row, and with them only in a 60,000-row user dimension that
                    the events reference by key. One user's personal columns are set to
                    NULL in each, and the table history says what was rewritten. A third
                    copy of the wide table, on plain Delta with deletion vectors, shows what
                    deferring the rewrite to a purge changes.
  audit             The auditor's question (Q13): who read personal data, by person and job,
                    from the platform's own records: the columns tagged personal in the
                    catalog, joined to the column lineage the platform records for every read.
                    Readers are pseudonymised in the result.

    python poc/databricks/governance.py erasure-by-model audit

Needs DATABRICKS_HOST, DATABRICKS_TOKEN and DATABRICKS_HTTP_PATH, and the speed test's data
(`workload.py load`). Writes results/poc-databricks-governance.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import ROOT, Databricks  # noqa: E402

RESULT = ROOT / "results" / "poc-databricks-governance.json"
SOURCE = "workspace.dpa_bi"
SCHEMA = "workspace.dpa_model"
USER = 7  # the person who asks to be erased
UNIFORM = ("'delta.enableIcebergCompatV2' = 'true', 'delta.universalFormat.enabledFormats' = 'iceberg', "
           "'delta.enableDeletionVectors' = 'false'")  # fmt: skip
METRICS = ("numRemovedFiles", "numAddedFiles", "numUpdatedRows", "numCopiedRows",
           "numDeletionVectorsAdded", "executionTimeMs")  # fmt: skip


def files(db: Databricks, table: str) -> dict:
    """The data files the table's current version reads, and how many rows it holds."""
    count, rows = db.sql(f"SELECT COUNT(DISTINCT _metadata.file_path), COUNT(*) FROM {table}")[0]
    return {"files": int(count), "rows": int(rows)}


def last_operation(db: Databricks, table: str) -> dict:
    cols = ", ".join(f"operationMetrics.{m}" for m in METRICS)
    row = db.sql(f"SELECT operation, {cols} FROM (DESCRIBE HISTORY {table}) ORDER BY version DESC LIMIT 1")[0]
    return {"operation": row[0], **{m: int(v or 0) for m, v in zip(METRICS, row[1:], strict=True)}}


def erase(db: Databricks, table: str) -> dict:
    """Remove one person's identity from a table: their personal columns become NULL."""
    before = files(db, table)
    rows = int(db.sql(f"SELECT COUNT(*) FROM {table} WHERE user_id = {USER}")[0][0])
    db.sql(f"UPDATE {table} SET email = NULL, full_name = NULL WHERE user_id = {USER}")
    return {"table": before, "rows_of_the_person": rows, "update": last_operation(db, table)}


def erasure_by_model(db: Databricks) -> dict:
    db.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    wide_select = (f"SELECT e.event_id, e.account_id, e.user_id, u.email, u.full_name, e.event_type, "
                   f"e.platform, e.event_at FROM {SOURCE}.events AS e JOIN {SOURCE}.users AS u "
                   f"ON u.user_id = e.user_id")  # fmt: skip
    db.sql(f"CREATE OR REPLACE TABLE {SCHEMA}.events_wide TBLPROPERTIES ({UNIFORM}) AS {wide_select}")
    db.sql(f"CREATE OR REPLACE TABLE {SCHEMA}.events_wide_dv "
           f"TBLPROPERTIES ('delta.enableDeletionVectors' = 'true') AS {wide_select}")  # fmt: skip
    db.sql(f"CREATE OR REPLACE TABLE {SCHEMA}.dim_user TBLPROPERTIES ({UNIFORM}) AS "
           f"SELECT user_id, account_id, email, full_name, role FROM {SOURCE}.users")  # fmt: skip
    out = {
        "personal_data_in_every_event": erase(db, f"{SCHEMA}.events_wide"),
        "personal_data_in_one_dimension": erase(db, f"{SCHEMA}.dim_user"),
        "personal_data_in_every_event_deletion_vectors": erase(db, f"{SCHEMA}.events_wide_dv"),
    }
    db.sql(f"REORG TABLE {SCHEMA}.events_wide_dv APPLY (PURGE)")
    out["personal_data_in_every_event_deletion_vectors"]["purge"] = last_operation(
        db, f"{SCHEMA}.events_wide_dv"
    )
    return out


def pseudonym(principal: str | None) -> str:
    """Readers appear in the evidence as a stable pseudonym, never as an identity."""
    if not principal:
        return "unknown"
    return "principal-" + hashlib.sha256(principal.encode()).hexdigest()[:8]


def audit(db: Databricks) -> dict:
    """Who read a column tagged personal, when, and through what: one query over the catalog's
    tags and the platform's column lineage."""
    query = """
        WITH personal AS (
            SELECT concat_ws('.', catalog_name, schema_name, table_name) AS table_name, column_name
            FROM workspace.information_schema.column_tags
            WHERE tag_name = 'class' AND tag_value = 'personal'
        )
        SELECT l.created_by, coalesce(l.entity_type, 'SQL query') AS through,
               p.table_name, p.column_name, COUNT(*) AS reads,
               MIN(l.event_time) AS first_read, MAX(l.event_time) AS last_read
        FROM system.access.column_lineage AS l
        JOIN personal AS p
          ON l.source_table_full_name = p.table_name AND l.source_column_name = p.column_name
        WHERE l.event_time >= current_timestamp() - INTERVAL 90 DAYS
        GROUP BY ALL
        ORDER BY reads DESC"""
    started = time.perf_counter()
    rows = db.sql(query)
    took = round(time.perf_counter() - started, 2)
    personal = int(db.sql("SELECT COUNT(*) FROM workspace.information_schema.column_tags "
                          "WHERE tag_name = 'class' AND tag_value = 'personal'")[0][0])  # fmt: skip
    return {
        "columns_tagged_personal": personal,
        "window_days": 90,
        "reads": [
            {
                "reader": pseudonym(r[0]),
                "through": r[1],
                "column": f"{r[2]}.{r[3]}",
                "reads": int(r[4]),
                "first": r[5],
                "last": r[6],
            }
            for r in rows
        ],  # fmt: skip
        "query_seconds": took,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("steps", nargs="+", choices=("erasure-by-model", "audit"))
    args = ap.parse_args()
    db = Databricks()
    result = json.loads(RESULT.read_text()) if RESULT.exists() else {}
    result["databricks_sql"] = db.sql("SELECT current_version().dbsql_version")[0][0]
    for step in args.steps:
        result[step] = {"erasure-by-model": erasure_by_model, "audit": audit}[step](db)
        RESULT.write_text(json.dumps(result, indent=2, default=str) + "\n")
        print(step, json.dumps(result[step], default=str)[:2000], flush=True)
    print(f"wrote {RESULT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
