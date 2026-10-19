"""Criterion 7 of the proof of concept: Terraform's coverage of the governance objects.

Applies poc/databricks/terraform/ (OpenTofu or Terraform, with the Databricks provider) and
records what Terraform owns, what it cannot, and whether a plan after the apply is clean:

  1. a targeted apply of the schema and the table;
  2. the mask function, with SQL: the provider has no resource for a Unity Catalog function;
  3. the full apply: the adopted governed tag, the column tags, the mask policy, the grants;
  4. a plan, which must show no changes;
  5. a row inserted and read back: the personal columns must come back masked;
  6. the schema and everything in it destroyed, the shared governed tag left in place.

    python poc/databricks/terraform.py      # writes results/poc-databricks-terraform.json

Needs DATABRICKS_HOST, DATABRICKS_TOKEN and DATABRICKS_HTTP_PATH, and `tofu` on the path
(set TF to use terraform instead).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import ROOT, Databricks  # noqa: E402

TF_DIR = HERE / "terraform"
RESULT = ROOT / "results" / "poc-databricks-terraform.json"
SCHEMA = "workspace.dpa_tf"
MASK = (f"CREATE OR REPLACE FUNCTION {SCHEMA}.mask_personal(v STRING) RETURN "
        "CASE WHEN is_account_group_member('personal_data_readers') THEN v ELSE '***' END")  # fmt: skip


def tf(*args: str, db: Databricks) -> dict:
    command = [os.environ.get("TF", "tofu"), *args, "-no-color"]
    env = {**os.environ, "TF_VAR_warehouse_id": db.warehouse}
    started = time.perf_counter()
    run = subprocess.run(command, cwd=TF_DIR, capture_output=True, text=True, env=env)
    out = {"command": " ".join(command[:2]), "exit": run.returncode,
           "seconds": round(time.perf_counter() - started, 1)}  # fmt: skip
    if run.returncode not in (0, 2):  # plan -detailed-exitcode returns 2 for changes
        out["error"] = (run.stderr or run.stdout)[-1500:]
    print(f"  {' '.join(args[:2])}: exit {run.returncode} in {out['seconds']} s", flush=True)
    return out


def main() -> None:
    db = Databricks()
    steps = {"init": tf("init", "-input=false", db=db)}
    targets = ["-target=databricks_schema.poc", "-target=databricks_sql_table.users"]
    steps["apply_schema_and_table"] = tf("apply", "-auto-approve", "-input=false", *targets, db=db)
    started = time.perf_counter()
    db.sql(MASK)
    steps["mask_function_by_sql"] = {"seconds": round(time.perf_counter() - started, 1)}
    steps["apply_all"] = tf("apply", "-auto-approve", "-input=false", db=db)
    steps["plan_after_apply"] = tf("plan", "-detailed-exitcode", "-input=false", db=db)
    state = subprocess.run([os.environ.get("TF", "tofu"), "state", "list"], cwd=TF_DIR,
                           capture_output=True, text=True).stdout.split()  # fmt: skip
    db.sql(f"INSERT INTO {SCHEMA}.users (user_id, email, full_name, role) "
           "VALUES (1, 'ana@example.test', 'Ana Example', 'admin')")  # fmt: skip
    row = db.sql(f"SELECT user_id, email, full_name, role FROM {SCHEMA}.users")[0]
    # Keep the governed tag, which the rest of the PoC uses; destroy the rest.
    subprocess.run([os.environ.get("TF", "tofu"), "state", "rm", "databricks_tag_policy.class"],
                   cwd=TF_DIR, capture_output=True, check=True)  # fmt: skip
    steps["destroy"] = tf("destroy", "-auto-approve", "-input=false", db=db)
    kinds = sorted({s.split(".")[0] for s in state})
    result = {
        "provider": "databricks/databricks 1.138.0",
        "tool": subprocess.run(
            [os.environ.get("TF", "tofu"), "version"], capture_output=True, text=True
        ).stdout.splitlines()[0],  # fmt: skip
        "steps": steps,
        "in_terraform": {"resources": len(state), "kinds": kinds},
        "outside_terraform": ["the mask function: no Unity Catalog function resource, created with SQL"],
        "plan_after_apply_clean": steps["plan_after_apply"]["exit"] == 0,
        "row_read_back": {"email": row[1], "full_name": row[2], "role": row[3]},
        "personal_columns_masked": row[1] == "***" and row[2] == "***",
    }
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "steps"}, indent=1))
    print(f"wrote {RESULT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
