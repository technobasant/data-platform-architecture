"""The Databricks half of the proof of concept (decision 0005): governance and erasure.

Three experiments on a Unity Catalog schema, through the SQL Statement Execution API:

  masking     A governed tag `class` (public, internal, confidential, personal). The product
              contract's tables are created with every column tagged from the contract's
              classification, and one schema-level policy masks every column tagged
              personal. A table created after the policy, with a personal column, is checked
              too: tagging it is all it should take.
  row_filter  A row filter keyed to the caller's identity (current_user() through a mapping
              table) scopes the events table to one account; moving the mapping moves the
              scope. A filter keyed to a session variable, the per-request value the
              assistant's tool could set, is attempted: functions cannot read one.
  erasure     One user's rows deleted from a Delta table, then followed to the point where no
              version of the table can return them: what the delete does (deletion vectors),
              what time travel still shows, what REORG ... APPLY (PURGE) rewrites, what VACUUM
              refuses, and, after the table's retention has passed, whether time travel to
              the version before the delete still works.

    python poc/databricks/run.py                       # all three; erasure waits an hour
    python poc/databricks/run.py --retention-hours 1

Needs DATABRICKS_HOST, DATABRICKS_TOKEN and DATABRICKS_HTTP_PATH (a SQL warehouse). Creates
and replaces the schema workspace.dpa_poc and the governed tag `class`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "results" / "poc-databricks.json"
SCHEMA = "workspace.dpa_poc"
CONTRACT = ROOT / "models" / "contracts" / "product-database.odcs.yaml"
CLASSES = ("public", "internal", "confidential", "personal")
TYPES = {"integer": "BIGINT", "string": "STRING", "number": "DECIMAL(10,2)", "timestamp": "TIMESTAMP"}


class Databricks:
    def __init__(self) -> None:
        self.host = os.environ["DATABRICKS_HOST"].rstrip("/")
        self.warehouse = os.environ["DATABRICKS_HTTP_PATH"].rstrip("/").rsplit("/", 1)[-1]
        self.http = httpx.Client(
            headers={"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}"}, timeout=120
        )

    def api(self, method: str, path: str, **kw) -> dict:
        r = self.http.request(method, f"{self.host}{path}", **kw)
        r.raise_for_status()
        return r.json() if r.content else {}

    def sql(self, statement: str) -> list[list]:
        d = self.api("POST", "/api/2.0/sql/statements",
                     json={"warehouse_id": self.warehouse, "statement": statement,
                           "wait_timeout": "50s", "on_wait_timeout": "CONTINUE"})  # fmt: skip
        while d["status"]["state"] in ("PENDING", "RUNNING"):
            time.sleep(2)
            d = self.api("GET", f"/api/2.0/sql/statements/{d['statement_id']}")
        if d["status"]["state"] != "SUCCEEDED":
            message = d["status"].get("error", {}).get("message", str(d["status"]))
            raise SQLError(message)
        return (d.get("result") or {}).get("data_array") or []

    def error(self, statement: str) -> str | None:
        """Run a statement expected to fail; its error class, or None if it succeeded."""
        try:
            self.sql(statement)
        except SQLError as e:
            found = re.search(r"\[([A-Z_.]+)\]|ErrorClass=([A-Z_.]+)", str(e))
            return next(g for g in found.groups() if g) if found else str(e)[:120]
        return None


class SQLError(RuntimeError):
    pass


def ensure_tag(db: Databricks) -> None:
    existing = {p["tag_key"] for p in db.api("GET", "/api/2.1/tag-policies").get("tag_policies", [])}
    if "class" not in existing:
        db.api("POST", "/api/2.1/tag-policies",
               json={"tag_key": "class", "description": "Data classification (data-platform-architecture)",
                     "values": [{"name": c} for c in CLASSES]})  # fmt: skip


def masking(db: Databricks) -> dict:
    """Tag every column from the contract; one policy masks every personal column."""
    contract = yaml.safe_load(CONTRACT.read_text())
    ensure_tag(db)
    db.sql(f"CREATE OR REPLACE FUNCTION {SCHEMA}.mask_personal(v STRING) RETURN "
           "CASE WHEN is_account_group_member('personal_data_readers') THEN v ELSE '***' END")  # fmt: skip
    personal, checked = [], []
    for table in contract["schema"]:
        cols = ", ".join(f"{p['name']} {TYPES[p['logicalType']]}" for p in table["properties"])
        db.sql(f"CREATE OR REPLACE TABLE {SCHEMA}.{table['name']} ({cols})")
        values = ", ".join(sample(p) for p in table["properties"])
        db.sql(f"INSERT INTO {SCHEMA}.{table['name']} VALUES ({values}), ({values})")
        for p in table["properties"]:
            db.sql(f"ALTER TABLE {SCHEMA}.{table['name']} ALTER COLUMN {p['name']} "
                   f"SET TAGS ('class' = '{p['classification']}')")  # fmt: skip
            if p["classification"] == "personal":
                personal.append((table["name"], p["name"]))
    db.error(f"DROP POLICY mask_personal ON SCHEMA {SCHEMA}")
    db.sql(
        f"CREATE POLICY mask_personal ON SCHEMA {SCHEMA} COLUMN MASK {SCHEMA}.mask_personal "
        "TO `account users` FOR TABLES MATCH COLUMNS has_tag_value('class', 'personal') AS c ON COLUMN c"
    )
    # A table that arrives after the policy, tagged and nothing else.
    db.sql(f"CREATE OR REPLACE TABLE {SCHEMA}.support_contacts (contact_id BIGINT, phone STRING)")
    db.sql(f"INSERT INTO {SCHEMA}.support_contacts VALUES (1, '+44 20 7946 0000')")
    db.sql(f"ALTER TABLE {SCHEMA}.support_contacts ALTER COLUMN phone SET TAGS ('class' = 'personal')")
    for table, column in [*personal, ("support_contacts", "phone")]:
        values = {r[0] for r in db.sql(f"SELECT {column} FROM {SCHEMA}.{table}")}
        checked.append({"column": f"{table}.{column}", "masked": values == {"***"}})
    others = db.sql(f"SELECT account_name, plan_id FROM {SCHEMA}.accounts LIMIT 1")[0]
    return {
        "columns_in_contract": sum(len(t["properties"]) for t in contract["schema"]),
        "personal_columns": len(personal),
        "checked": checked,
        "masked": sum(c["masked"] for c in checked),
        "added_after_policy_masked": checked[-1]["masked"],
        "non_personal_readable": "***" not in others,
    }


def sample(p: dict) -> str:
    return {"integer": "1", "number": "49.00", "timestamp": "TIMESTAMP '2026-09-01 00:00:00'"}.get(
        p["logicalType"], f"'{p['name']}-value'"
    )


def row_filter(db: Databricks) -> dict:
    """Scope rows by the caller's identity; try to scope them by a session variable."""
    me = db.sql("SELECT current_user()")[0][0]
    db.sql(f"CREATE OR REPLACE TABLE {SCHEMA}.events_scoped (account_id BIGINT, events INT)")
    db.sql(f"INSERT INTO {SCHEMA}.events_scoped SELECT id % 5 + 1, 1 FROM range(1000)")
    total = int(db.sql(f"SELECT COUNT(DISTINCT account_id) FROM {SCHEMA}.events_scoped")[0][0])
    db.sql(f"CREATE OR REPLACE TABLE {SCHEMA}.caller_accounts (principal STRING, account_id BIGINT)")
    mapping = f"SELECT a.account_id FROM {SCHEMA}.caller_accounts AS a WHERE a.principal = current_user()"
    db.sql(f"CREATE OR REPLACE FUNCTION {SCHEMA}.own_account(account_id BIGINT) "
           f"RETURN account_id IN ({mapping})")  # fmt: skip
    db.sql(f"ALTER TABLE {SCHEMA}.events_scoped SET ROW FILTER {SCHEMA}.own_account ON (account_id)")
    seen = {}
    for account in (2, 4):
        db.sql(f"DELETE FROM {SCHEMA}.caller_accounts")
        db.sql(f"INSERT INTO {SCHEMA}.caller_accounts VALUES ('{me}', {account})")
        accounts, rows = db.sql(f"SELECT COUNT(DISTINCT account_id), COUNT(*) FROM {SCHEMA}.events_scoped")[0]
        only = db.sql(f"SELECT MIN(account_id) FROM {SCHEMA}.events_scoped")[0][0]
        seen[f"mapped_to_{account}"] = {"accounts_visible": int(accounts), "rows": int(rows), "account": only}
    db.sql("DECLARE OR REPLACE VARIABLE request_account BIGINT DEFAULT 1")
    fn = f"{SCHEMA}.request_account_only(account_id BIGINT)"
    session_variable = db.error(f"CREATE OR REPLACE FUNCTION {fn} RETURN account_id = request_account")
    return {"accounts_in_table": total, **seen,
            "filter_on_a_session_variable": session_variable or "created"}  # fmt: skip


def user_rows(db: Databricks, table: str, version: int | None = None) -> int:
    """Rows of the erased user (user_id 7), now or at a version."""
    at = f" VERSION AS OF {version}" if version is not None else ""
    return int(db.sql(f"SELECT COUNT(*) FROM {table}{at} WHERE user_id = 7")[0][0])


def erasure(db: Databricks, retention_hours: int) -> dict:
    """Follow one user's rows from DELETE to unrecoverable."""
    t = f"{SCHEMA}.user_events"
    db.sql(
        f"CREATE OR REPLACE TABLE {t} (user_id BIGINT, email STRING, event_type STRING) "
        "TBLPROPERTIES ('delta.enableDeletionVectors' = 'true')"
    )
    db.sql(
        f"INSERT INTO {t} SELECT id % 50, concat('user', id % 50, '@example.test'), 'login' FROM range(5000)"
    )
    before = int(db.sql(f"SELECT MAX(version) FROM (DESCRIBE HISTORY {t})")[0][0])
    out = {"rows_of_the_user": user_rows(db, t)}
    db.sql(f"DELETE FROM {t} WHERE user_id = 7")
    hist = db.sql(f"SELECT operationMetrics.numDeletionVectorsAdded, operationMetrics.numRemovedFiles "
                  f"FROM (DESCRIBE HISTORY {t}) WHERE operation = 'DELETE'")[0]  # fmt: skip
    out["after_delete"] = {
        "current_rows": user_rows(db, t),
        "time_travel_rows": user_rows(db, t, before),
        "deletion_vectors_added": int(hist[0] or 0),
        "files_rewritten": int(hist[1] or 0),
    }  # fmt: skip
    db.sql(f"REORG TABLE {t} APPLY (PURGE)")
    metrics = "operationMetrics.numRemovedFiles, operationMetrics.numAddedFiles, operation"
    purge = db.sql(f"SELECT {metrics} FROM (DESCRIBE HISTORY {t}) ORDER BY version DESC LIMIT 1")
    out["after_purge"] = {
        "operation": purge[0][2] if purge else None,
        "files_removed": int(purge[0][0] or 0) if purge else None,
        "files_added": int(purge[0][1] or 0) if purge else None,
        "time_travel_rows": user_rows(db, t, before),
    }  # fmt: skip
    out["vacuum_retain_0_hours"] = db.error(f"VACUUM {t} RETAIN 0 HOURS") or "ran"
    out["vacuum_default_now"] = db.error(f"VACUUM {t}") or "ran"
    out["time_travel_after_default_vacuum"] = int(
        db.sql(f"SELECT COUNT(*) FROM {t} VERSION AS OF {before} WHERE user_id = 7")[0][0]
    )
    db.sql(f"ALTER TABLE {t} SET TBLPROPERTIES ('delta.deletedFileRetentionDuration' = "
           f"'interval {retention_hours} hours')")  # fmt: skip
    print(f"  erasure: waiting {retention_hours} h for the table's retention to pass", flush=True)
    time.sleep(retention_hours * 3600 + 120)
    out["vacuum_after_retention"] = db.error(f"VACUUM {t} RETAIN {retention_hours} HOURS") or "ran"
    out["time_travel_after_retention"] = db.error(f"SELECT COUNT(*) FROM {t} VERSION AS OF {before}") or "ran"
    out["current_rows_after"] = user_rows(db, t)
    out["retention_hours"] = retention_hours
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retention-hours", type=int, default=1)
    args = ap.parse_args()
    db = Databricks()
    db.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    version = db.sql("SELECT current_version().dbsql_version")[0][0]
    started = datetime.now(UTC).isoformat(timespec="seconds")
    result = {"databricks_sql": version, "started": started}
    result["masking"] = masking(db)
    print("masking:", json.dumps({k: v for k, v in result["masking"].items() if k != "checked"}), flush=True)
    result["row_filter"] = row_filter(db)
    print("row filter:", json.dumps(result["row_filter"]), flush=True)
    result["erasure"] = erasure(db, args.retention_hours)
    print("erasure:", json.dumps(result["erasure"]), flush=True)
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {RESULT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
