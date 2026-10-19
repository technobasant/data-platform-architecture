# 11. Proof of concept: the Databricks half

[0005](../decisions/0005-databricks-or-snowflake.md) decides between Databricks and Snowflake by
a two-week proof of concept on criteria fixed in advance. This is the part run so far:
every criterion on Databricks. The Snowflake half waits for a trial account; until both
halves are in, 0005 stays Proposed.

Everything here ran on Databricks Free Edition (Databricks SQL 2026.39, Unity Catalog, one
serverless SQL warehouse of the smallest size, 2X-Small), by
[`poc/databricks/run.py`](../poc/databricks/run.py) (governance and erasure,
[`results/poc-databricks.json`](../results/poc-databricks.json)),
[`poc/databricks/workload.py`](../poc/databricks/workload.py) (speed and cost,
[`results/poc-databricks-workload.json`](../results/poc-databricks-workload.json)) and
[`poc/databricks/terraform.py`](../poc/databricks/terraform.py) (operability,
[`results/poc-databricks-terraform.json`](../results/poc-databricks-terraform.json)).
Free Edition runs no bill; the cost below is what its billing table records, priced at list.

| # | Criterion | Databricks | Snowflake |
|---|---|---|---|
| 1 | The dbt project builds unchanged; revenue reconciles | **passed with one change**: 11 models, 46 data tests and 3 unit tests; revenue figures identical to DuckDB's ([data-stack-lab](https://github.com/technobasant/data-stack-lab/tree/main/databricks)) | waiting for a trial |
| 2 | Ingestion: corrected, late and duplicate files; CDC | measured in [data-stack-lab](https://github.com/technobasant/data-stack-lab/tree/main/databricks): only Auto Loader with `allowOverwrites` and a `MERGE` was exact | waiting for a trial |
| 3 | Governance: masking and row filters | **measured, below** | waiting for a trial |
| 4 | Erasure through time travel | **measured, below** | waiting for a trial |
| 5 | Cost from the billing tables | **measured, below**: a day's build and reports took 38 s and were billed 0.743 DBU, 95% of it the auto-stop wait; $21 to $961 a month at EU list price by how often the warehouse wakes, far inside the budget | waiting for a trial |
| 6 | Speed of the BI query set | **measured, below**: every query under 3 s at concurrency 8, on the smallest warehouse | not yet run |
| 7 | Operability and Terraform coverage | **measured, below**: Terraform owned the governed tag, schema, table, column tags, mask policy and grants, and planned clean after applying; the mask function needs SQL | waiting for a trial |

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

On the format the design chose, Delta with UniForm so other engines read it as Iceberg
([0006](../decisions/0006-open-format-in-the-clients-account.md)), the same steps go
differently:

| Step, on a UniForm table | The user's rows, current table | By time travel to before the delete |
|---|---:|---:|
| Create it with deletion vectors | refused: `DELTA_ICEBERG_COMPAT_VIOLATION.DELETION_VECTORS_SHOULD_BE_DISABLED` | |
| `DELETE`: 0 deletion vectors, 8 files removed, 1 written | 0 | **100** |
| `VACUUM`, default retention (7 days) | 0 | **100** |
| `VACUUM` after the table's retention (1 hour for the test) had passed | 0 | refused |

UniForm refuses deletion vectors, so the `DELETE` rewrites every file that holds the user's
rows and no purge is needed. The old files stay reachable by time travel for the same
retention, so the timeline is the same; what changes is that every row-level change, the
weekly erasure and the CDC merges included, rewrites whole files.

For [0012](../decisions/0012-erasure.md) on Databricks: delete by key, purge, and `VACUUM` once
the retention has passed. With the default 7-day retention, a weekly erasure job and a daily
`VACUUM`, a request is unrecoverable within 15 days, inside the 30 the DPA allows, and the
7-day restore window of [0015](../decisions/0015-restore-points.md) is kept. The table's
retention is the lever: shortening it shortens both.

## Speed: the BI query set

The four queries the BI tool runs against the product's database today
([`baseline/analytics.sql`](../baseline/analytics.sql)), unchanged but for the timestamp
literals, on the same data at today's scale: 6,000 accounts, 60,000 users, 70,470 invoices
and 90 days of events, 31.5 million rows, generated in Databricks as `baseline/` generates
them for Postgres. Each analyst had a session of their own with the result cache switched
off, so every query was executed (the query history confirms none came from the cache);
timings are the warehouse's own, from `system.query.history`, after one warm-up pass.

| Query (median seconds) | Postgres primary, 2 analysts, product at its peak rate | Databricks 2X-Small, 2 analysts | Databricks 2X-Small, 8 analysts |
|---|---:|---:|---:|
| Daily active users by plan, 90 days | 62.0 | 1.52 | 2.82 |
| Weekly event mix | 90.2 | 1.19 | 2.31 |
| Top accounts, last 30 days | 24.4 | 0.50 | 0.78 |
| Revenue by plan and month | 0.4 | 0.64 | 0.91 |

The smallest warehouse ran the reports that take a minute or more on the product's database in
one to three seconds. With eight analysts at once, no query waited for capacity: the one
cluster ran them together, each about twice as slowly, and the 95th percentile was 2.9 s. The
revenue report, which reads a few thousand rows, was faster on Postgres; nothing reads a small
table faster than a warm database it already lives in.

The comparison is not like for like, and is not meant to be: the Postgres figures are the
client's lab database on 2 vCPU under the product's own load, and the warehouse is a managed
service of undisclosed hardware. What it shows is the order of magnitude the client buys:
interactive dashboards on the full history, with no load on the product.

## Cost: what the billing table charged

One day of the client's work on the same 2X-Small warehouse, alone in a clock hour from a
stopped warehouse, so the hour's billing rows belong to it: the daily build (30 September's
350,000 events loaded with `INSERT … REPLACE WHERE`, the usage mart's last three days
replaced as [0008](../decisions/0008-incremental-by-interval.md) has it, the mart contract's
quality check), then the four reports once by each of two analysts. Then the warehouse was
left to stop itself, after the default 10 minutes idle.

| | |
|---|---|
| Work, first statement to last | 38 s (the build 23.7 s, the reports 7.5 s) |
| Running, from `system.compute.warehouse_events` | 11 min 9 s |
| Billed, from `system.billing.usage` | **0.743 DBU**, at 4 DBU an hour of uptime |
| Of the bill, the wait after the last statement | 95% (10 min 33 s) |

The billing table charges uptime at the size's rate, whatever runs: in three other hours
the same warehouse was up 54.2, 33.45 and 27.37 minutes and was charged 3.614, 2.230 and
1.825 DBU, again 4 an hour. The work does not set the bill; how often the warehouse wakes does. At list price
in the client's region (serverless SQL $0.91 a DBU in AWS EU Ireland, so $3.64 an hour for
a 2X-Small):

| How the warehouse is used | Hours awake a month | A month at list price |
|---|---:|---:|
| Woken once a day for the build and the reports | 5.6 | $21 |
| The build, and reports in six separate sessions on working days | about 30 | about $109 |
| Awake through EU working hours | 264 | $961 |
| Awake all month | 730 | $2,657 |

The cost model's assumption for Databricks today, 1.5 hours a day of a Medium warehouse
([`cost/workloads.yml`](../cost/workloads.yml)), is $996 a month at the same price: about what
the smallest size costs awake through every working hour, and more than the measured work
needs. At 36 months the data is about 14 times larger; if report time grows with the rows
read, keeping the reports to seconds takes a Small or a Medium (4 and 8 times the workers),
$2,883 to $5,766 a month awake through working hours: inside the budget either way. Criterion
5 passes on Databricks; the number that matters for the client is the hours awake, which is
set by auto-stop, by how analysts use dashboards, and by keeping always-on consumers off the
warehouse. The stage-3 assistant is one: a warehouse kept awake for it would cost $2,657 a
month at the smallest size, more than its own budget, so its queries go to the stage-2 store
([ai-platform-architecture 0014](https://github.com/technobasant/ai-platform-architecture/blob/main/decisions/0014-cost-per-answer.md)).

## Operability: what Terraform can own

The governance above was built by API and SQL. [`poc/databricks/terraform/`](../poc/databricks/terraform/main.tf)
declares the same objects in a schema of their own, and
[`terraform.py`](../poc/databricks/terraform.py) applies them from an empty state, plans
again, checks the result and destroys it (OpenTofu 1.13.1, Databricks provider 1.138.0).

| Object | Resource | In Terraform |
|---|---|---|
| The governed tag `class`, created earlier through the API | `databricks_tag_policy`, adopted with an `import` block | ✔ |
| The schema and the `users` table | `databricks_schema`, `databricks_sql_table` | ✔ |
| Each column's classification, from the contract | `databricks_entity_tag_assignment` (4) | ✔ |
| The schema's mask policy, matching `has_tag_value('class', 'personal')` | `databricks_policy_info` | ✔ |
| Grants on the schema | `databricks_grants` | ✔ |
| The mask function the policy calls | none: the provider has no resource for a Unity Catalog function | ✘ SQL |

| Step | Exit | Seconds |
|---|---:|---:|
| Apply the schema and the table, targeted | 0 | 7.8 |
| Create the mask function, SQL | | 2.0 |
| Apply everything | 0 | 6.8 |
| Plan again | 0, no changes | 3.8 |
| Destroy, the shared tag left in place | 0 | 10.0 |

Nine resources, and a plan with no changes after the apply. A row inserted into the
Terraform-built table read back with `email` and `full_name` as `***` and `role` readable:
the policy Terraform declared, on the tags Terraform set, did the masking.

The gap is the function. A policy and the function it calls are in different tools, so on an
empty workspace the policy cannot be applied until the function exists: the deployment is
two applies with a SQL step between them, or a SQL migration that runs before Terraform's
policy step, and a change to the function is reviewed like a change to the policy. The same
resource declares attribute-based row filters, which were not exercised here. Nothing
broke on the platform's side; the one failure in the run was in my own check, which inserted
values in declared order while Terraform had created the columns in a map's key order.

---

[← 10. Roadmap](10-roadmap.md) · [README](../README.md) · [12. SOC 2 readiness →](12-soc2-readiness.md)
