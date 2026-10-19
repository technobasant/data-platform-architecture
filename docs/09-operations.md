# 9. Operations

How a team of two to four runs the platform without anyone on call at night
([Q15](03-requirements.md)). Nothing customer-facing depends on the platform in stage 1,
so its failures wait for business hours; the one exception, WAL retained on the product's
database by a stalled CDC slot, pages the product's on-call.

## What is watched

| Signal | Threshold | Goes to | Why |
|---|---|---|---|
| WAL retained by the CDC slot on RDS | 20% of free storage | the product's on-call | the only way the platform can hurt the product |
| CDC lag, raw behind the product | 30 min | data team, business hours | Q5 at risk |
| Each mart's last successful build | 06:00 UTC | data team | Q5 |
| A day held by a quality gate | any | data team | [0014](../decisions/0014-quality-gates.md) |
| Per-day event count, for days the product has already purged | falls below yesterday's count for that day | data team | the platform should ignore the product's 90-day purge on `events` ([0002](../decisions/0002-cdc-from-the-product-database.md)); a fall means a delete leaked through |
| Platform spend against the monthly budget | 50%, 80%, 100% of pro-rata | data lead, CFO at 100% | Q14 |
| Isolation and tag-coverage tests | any failure | data team, blocks deploy | Q11 |

## Runbooks

### Re-run or backfill a range of days

- **When:** a model changed, or a source re-delivered history.
- **Do:** run the dbt job with the window as a parameter, one window per day; order does
  not matter for window-replacing models ([0008](../decisions/0008-incremental-by-interval.md)).
- **Verify:** per-day row counts against `raw`; no day doubled.
- **Never:** use a high-water-mark model for a backfill without a full refresh after it.
  Newest-first, two such models lost 96.56% of a month with every run green
  ([rehearsed](https://github.com/technobasant/data-stack-lab/tree/main/airflow)).

### A file arrives late, truncated or corrected

- **Late:** nothing to do; the file-tracking loader picks it up and the look-back window
  includes its day.
- **Truncated:** the manifest check holds the day; ask the producer to re-send **under a new
  name**.
- **Re-sent under the same name:** it will not be read
  ([measured](https://github.com/technobasant/data-stack-lab/tree/main/databricks)). Copy it
  to a new name, or load it explicitly, then let the `MERGE` resolve duplicates.

### The CDC slot stalls, or is lost

- **Stalls:** restart the connector; WAL drains. If retained WAL nears the threshold and the
  connector cannot catch up, drop the slot: the product comes first.
- **Lost** (RDS failover or major-version upgrade): recreate the slot and re-snapshot the
  captured tables. Changes during the gap are lost to history; record the gap in `audit`.
- **Before an RDS major-version upgrade:** plan the re-snapshot with the product team.

### A bad write

- **Do:** restore the table to the last version before it
  ([0015](../decisions/0015-restore-points.md)), then re-run the windows written since.
- **Rehearsed:** a Delta table overwritten to 1 day of 365 was restored to 365 by one
  statement ([data-stack-lab](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md));
  quarterly drill on a copy of a production table, timed.
- **If the bucket itself is gone** (a bucket, key or Terraform mistake): restore it from the
  AWS Backup vault in the separate AWS account, then re-apply the erasure log before anyone
  reads the restored data ([0015](../decisions/0015-restore-points.md)).

### A producer wants a breaking change

- **Signal:** `datacontract breaking` fails in the producer's CI.
- **Do:** agree a migration: add the new column, backfill, move consumers, remove the old
  one in a later version ([0013](../decisions/0013-contracts-at-the-producer.md)).

### An erasure request

- **Do:** run the erasure job for the user within 7 days; it deletes by key in every layer.
- **After day 30:** run the proof query and store the result
  ([7. Security and governance](07-security-and-governance.md)).

### The bill jumps

- **Do:** find the job or user in the platform's billing tables by tag; stop it; cap the
  warehouse size or the serverless budget; fix the query.

## Change and release

- Platform objects (catalogs, schemas, roles, grants, policies, warehouses, budgets) are
  Terraform, applied from CI after review; no change by hand in production.
- dbt runs in CI against a development environment with a sample of production, including
  unit tests and deliberate breaks, before a merge.
- Upgrades of the platform's runtime are the vendor's; the team tests dbt against a new
  runtime in development before production moves.
