# 11. Proof of concept: the Databricks half

[0005](../decisions/0005-databricks-or-snowflake.md) decides between Databricks and Snowflake by
a two-week proof of concept on criteria fixed in advance. This is the part run so far: the
governance and erasure criteria on Databricks. The Snowflake half waits for a trial account;
until both halves are in, 0005 stays Proposed.

Everything here was run by [`poc/databricks/run.py`](../poc/databricks/run.py) on Databricks
Free Edition (Databricks SQL 2026.39, Unity Catalog, the serverless SQL warehouse), and is in
[`results/poc-databricks.json`](../results/poc-databricks.json).

| # | Criterion | Databricks | Snowflake |
|---|---|---|---|
| 1 | The dbt project builds unchanged; revenue reconciles | **passed with one change**: 11 models, 46 data tests and 3 unit tests; revenue figures identical to DuckDB's ([data-stack-lab](https://github.com/technobasant/data-stack-lab/tree/main/databricks)) | waiting for a trial |
| 2 | Ingestion: corrected, late and duplicate files; CDC | measured in [data-stack-lab](https://github.com/technobasant/data-stack-lab/tree/main/databricks): only Auto Loader with `allowOverwrites` and a `MERGE` was exact | waiting for a trial |
| 3 | Governance: masking and row filters | **measured, below** | waiting for a trial |
| 4 | Erasure through time travel | **measured, below** | waiting for a trial |
| 5 | Cost from the billing tables | the billing tables are readable (`system.billing.usage`); not yet run on the workload | waiting for a trial |
| 6 | Speed of the BI query set | not yet run | not yet run |
| 7 | Operability and Terraform coverage | the tag policy, masks and row filters were all created by API and SQL, so Terraform can own them | waiting for a trial |

## Governance: masking by classification

The design in [0011](../decisions/0011-tags-drive-masking-and-row-filters.md) is that every
column carries its classification from its contract, and masking follows the tag, so a new
personal column is masked the day it ships.

- A governed tag `class` with the values public, internal, confidential and personal (a tag
  policy: Unity Catalog's attribute-based policies refuse an ungoverned tag key).
- The product contract's four tables created, and every one of their 26 columns tagged from
  the contract's classification.
- One schema-level policy: a column mask for every column where `class = personal`.

| Columns in the contract, tagged | Personal | Masked by the one policy | Added after the policy, masked | Other columns readable |
|---:|---:|---:|---|---|
| 26 | 2 (`users.email`, `users.full_name`) | 3 of 3 | yes: `support_contacts.phone`, tagged and nothing else | yes |

Nobody wrote a mask for a column. The one thing that made a new personal column masked was
its tag, which the build sets from the contract.

## Governance: row filters and the caller's identity

- A row filter keyed to `current_user()` through a mapping table scopes a five-account table
  to the mapped account; moving the mapping moves the scope.
- A row filter keyed to a session variable, the per-request value a service such as the
  usage assistant could set, cannot be created: a function cannot read a session variable.

| Row filter keyed to | Accounts in the table | Visible to the caller |
|---|---:|---|
| `current_user()`, mapped to account 2 | 5 | 1 account (200 rows, account 2) |
| the same, the mapping moved to account 4 | 5 | 1 account (account 4) |
| a session variable set per request | | cannot be created: `UNRESOLVED_COLUMN` |

The consequence for the stage-3 assistant, whose users are customers rather than platform
users, is in the AI architecture's
[0011](https://github.com/technobasant/ai-platform-architecture/blob/main/decisions/0011-identity-on-the-platform.md):
the assistant's tool scopes each query by rewriting it, measured to return exactly what
row-level security returns.

## Erasure through time travel

The design in [0012](../decisions/0012-erasure.md) is that an erasure deletes by key and then
lets every version that still holds the rows expire inside 30 days. Followed on a Delta table
with deletion vectors, from `DELETE` to the point where no version returns the user's rows:

| Step | The user's rows, current table | The same rows, by time travel to before the delete |
|---|---:|---:|
| Before | 100 | |
| `DELETE`: 8 deletion vectors written, 0 files rewritten | 0 | **100** |
| `REORG TABLE … APPLY (PURGE)`: 8 files rewritten without the rows | 0 | **100** |
| `VACUUM … RETAIN 0 HOURS` | refused: `DELTA_VACUUM_RETENTION_PERIOD_TOO_SHORT` | |
| `VACUUM`, default retention (7 days) | 0 | **100** |
| `VACUUM` after the table's retention (set to 1 hour for the test) had passed | 0 | refused: `DELTA_UNSUPPORTED_TIME_TRAVEL_BEYOND_DELETED_FILE_RETENTION_DURATION` |

A `DELETE` on a table with deletion vectors rewrites nothing: the rows stay in the data files,
marked deleted, and every earlier version still returns them. `REORG … APPLY (PURGE)` writes
files without them, and the earlier versions still return them from the old files. Only
when the table's deleted-file retention has passed does `VACUUM` remove the old files, after
which Databricks refuses time travel to those versions. `VACUUM` refuses a shorter retention
than the table's setting unless a safety check is switched off, which the erasure design does
not do.

For [0012](../decisions/0012-erasure.md) on Databricks: delete by key, purge, and `VACUUM` once
the retention has passed. With the default 7-day retention and a weekly erasure job, a
request is unrecoverable within 14 days, inside the 30 the DPA allows, and the 7-day restore
window of [0015](../decisions/0015-restore-points.md) is kept. The table's retention is the
lever: shortening it shortens both.
