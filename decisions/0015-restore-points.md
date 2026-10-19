# 0015. Every analytical table can be restored to any point in the last 7 days

- Status: Accepted
- Date: 2026-10-19
- Deciders: CTO, data lead; proposed by the architect
- Evidence: dsl_delta_restore, lakehouse_rollback

## Context

The most likely data incident on the platform is a bad write: an overwrite that replaces a
whole table, a delete with the wrong predicate, a backfill of the wrong window. They are
usually noticed days later, by a person looking at a number.

## Decision drivers

- Q9: a bad write found up to 7 days later is undone within an hour.
- Q10: erasure inside 30 days limits how long old versions may be kept.
- No separate backup system for a team of two.
- The platform's own bucket is the only copy of events older than 90 days: a bucket, key or
  Terraform mistake that destroys it is not covered by table versions, which live in the
  same bucket.

## Options

| | Undo a bad write from 7 days ago | Effort | Fits erasure |
|---|---|---|---|
| Rebuild from raw | ◐ only for derived tables | ✘ hours to days | ✔ |
| Nightly copies of every table | ✔ | ✘ storage and a copy job | ✘ more copies to erase |
| **The table format's own versions (Delta `RESTORE`, Snowflake Time Travel), 7-day window, drilled quarterly** | ✔ | ✔ | ✔ with [0012](0012-erasure.md) |

## Decision

Analytical tables keep 7 days of versions in the table format itself, and are restored with
the platform's restore statement. Raw layers can also be rebuilt from the landed files
while they still exist, for the 30 days before each expires by S3 lifecycle
([0003](0003-files-immutable-loads-by-key.md)); beyond that, the raw tables are the
rebuild source. A restore drill runs every quarter on a copy of a production table and is
timed.

### A copy outside the bucket

Table versions undo a bad write; they do not survive losing the bucket itself. AWS Backup
copies the bucket into a backup vault in a separate AWS account, retained 14 days. A restore
from the vault re-applies the erasure log before anyone reads the restored data, so an
erased person does not reappear through it. The KMS key's policy denies
`ScheduleKeyDeletion` except to a break-glass role, and keeps the 30-day pending window, so
the key cannot be destroyed along with the bucket by the same mistake.

Combined with erasure being unrecoverable on the platform within 15 days
([0012](0012-erasure.md)), an erased person's data is gone from the backup vault within
15 + 14 = 29 days, inside the 30 the DPA allows.

## Consequences

- An overwrite that leaves 1 day of 365 is a one-statement fix within the window, not a
  rebuild.
- Version retention is a storage cost and an erasure constraint at once; 7 days satisfies
  both.
- A mistake noticed after 7 days needs a rebuild from raw, or, if the bucket itself is gone,
  a restore from the backup vault followed by the erasure log.
- A bucket, key or Terraform mistake that destroys the platform's history is caught by the
  backup vault instead of being unrecoverable
  ([failure modes](../docs/05-target-architecture.md#how-each-part-fails), [risks](../docs/risks.md)).

## Revisit when

A bad write goes unnoticed for more than 7 days, which is a monitoring gap before it is a
retention gap.

## Evidence

<!-- evidence:start -->
- **365 of 365** days back after RESTORE TABLE, following an INSERT OVERWRITE of one day that left 1. Databricks SQL 2026.39 on Free Edition: a 365-day rollup (333,082 rows) as a Delta table partitioned by day; 15 September rewritten with INSERT OVERWRITE, then RESTORE TABLE TO VERSION AS OF 0. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- Indirect: rollback measured on the self-run Iceberg lakehouse in lakehouse-lab, not on the managed platform's own restore feature. **909,968** rows recovered by snapshot rollback. An over-broad DELETE (a WHERE reaching years further back than intended), then ALTER TABLE EXECUTE rollback_to_snapshot, counted against the pre-incident total. Source: [lakehouse-lab/MEASUREMENTS.md](https://github.com/technobasant/lakehouse-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
