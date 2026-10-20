# 0006. Tables are kept in an open format, in storage the company owns

- Status: Accepted
- Date: 2026-10-19
- Deciders: CTO, CFO; proposed by the architect
- Evidence: lakehouse_rollback, lakehouse_partition_prune, dpa_erasure_uniform

## Context

A managed platform ([0004](0004-managed-platform.md)) brings the risk of being unable to
leave it, or of paying to read one's own data with only one engine. The analytical history
is the company's most valuable data asset after the product database, and it will be read
by engines that do not exist yet in the company's stack: the assistant in stage 3, and
possibly a serving store in stage 2.

## Decision drivers

- Leaving later at a cost proportional to the work, not to the data.
- One copy of the data, readable by more than one engine.
- Erasure that reaches every copy (Q10): fewer copies, fewer places to erase.
- The vendor's own features (performance, governance) must still work.

## Options

| | Leave later | One copy, many engines | Vendor features intact |
|---|---|---|---|
| Vendor-managed native tables | ✘ an export of everything | ✘ | ✔ |
| **Open table format in the company's S3, governed by the platform's catalog** (Delta with UniForm, or Snowflake-managed Iceberg) | ✔ | ✔ read as Iceberg | ◐ some features are native-only |
| Open tables governed by an independent catalog | ✔ | ✔ | ✘ the platform's governance does not apply |

## Decision

Analytical tables are stored in an open table format in an S3 bucket the company owns,
registered in the chosen platform's catalog: Delta with UniForm (readable as Iceberg) on
Databricks, or Snowflake-managed Iceberg tables on Snowflake. Where a feature needed for a
requirement exists only for native tables, the exception is written down in the
platform's decision record when [0005](0005-databricks-or-snowflake.md) is accepted.

## Consequences

- The bucket, its encryption key and its lifecycle rules are the company's, in Terraform,
  and are part of the erasure and backup design.
- A second engine can read without copying, under the platform catalog's credentials.
- Some platform features behave differently or cost more on open tables. Measured on
  Databricks: UniForm refuses deletion vectors (`DELTA_ICEBERG_COMPAT_VIOLATION`), so every
  `DELETE`, `UPDATE` and `MERGE` rewrites the files it touches; deleting one user's rows
  rewrote all 8 files that held them. The erasure timeline is unchanged, since the retention
  bounds it ([0012](0012-erasure.md)); the write cost of row-level changes grows with file
  size, and is watched in the weekly erasure job and the CDC merges.

## Revisit when

The proof of concept shows a requirement that cannot be met on the open format.

## Evidence

<!-- evidence:start -->
- Indirect: rollback measured on the self-run Iceberg lakehouse in lakehouse-lab, not on the managed platform's own restore feature. **909,968** rows recovered by snapshot rollback. An over-broad DELETE (a WHERE reaching years further back than intended), then ALTER TABLE EXECUTE rollback_to_snapshot, counted against the pre-incident total. Source: [lakehouse-lab/MEASUREMENTS.md](https://github.com/technobasant/lakehouse-lab/blob/main/MEASUREMENTS.md)
- Indirect: partition pruning measured by Trino reading Iceberg tables in lakehouse-lab, a second engine reading the open format, not UniForm itself. **88 ms** one-month predicate over 1.5M Iceberg rows. Median of 7 server-side runs from system.runtime.queries, after 2 warm-ups, on a month-partitioned Iceberg table. Source: [lakehouse-lab/MEASUREMENTS.md](https://github.com/technobasant/lakehouse-lab/blob/main/MEASUREMENTS.md)
- **8 files** rewritten by deleting one user's rows from a UniForm table, which refuses deletion vectors; time travel still returned all 100 rows until the retention passed. Databricks SQL 2026.39 on Free Edition: a Delta table with delta.enableIcebergCompatV2 and Iceberg as a universal format; creating it with deletion vectors failed with DELTA_ICEBERG_COMPAT_VIOLATION.DELETION_VECTORS_SHOULD_BE_DISABLED; DELETE removed 8 files and added 1; time travel refused only after a 1-hour retention and VACUUM. Source: [data-platform-architecture/results/poc-databricks.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks.json)
<!-- evidence:end -->
