# Decisions

The architecture decisions for the client in [the brief](../docs/01-brief.md), one file each.

Every record follows the same template, and `scripts/build.py --check` fails CI if one does
not:

- **Status:** Accepted, Proposed (waiting for a measurement or for its stage to start), or
  Superseded.
- **Context:** the problem, in the client's terms.
- **Decision drivers:** the requirements and constraints that decide it, by number where
  [3. Requirements](../docs/03-requirements.md) has one.
- **Options:** the realistic alternatives, scored against the drivers.
- **Decision**, and **Consequences**: what it costs, what it makes harder, and how easily it
  can be undone.
- **Revisit when:** the observable condition that should reopen it.
- **Evidence:** measured results, generated from
  [`../evidence/evidence.yml`](../evidence/evidence.yml). A record is Accepted only if it
  cites at least one.

<!-- decisions:start -->
| # | Decision | Status | Backed by |
|---|---|---|---|
| 0001 | [Analytics moves off the product's database onto a separate platform](0001-analytics-off-the-product-database.md) | Accepted | 93 → 794 ms product p95 request latency, without and with the BI tool's reports on the primary; 3 of 412 runs of the three long reports that finished on the read replica in five minutes; 409 were cancelled by recovery conflicts |
| 0002 | [The product's tables reach the platform by change data capture, not extracts](0002-cdc-from-the-product-database.md) | Accepted | 533 of 570 account changes in a year seen by monthly snapshots; 15.1% of a year's revenue on the wrong plan with a Type 1 account dimension |
| 0003 | [Files that land are immutable, and every load writes by key](0003-files-immutable-loads-by-key.md) | Accepted | 1,638 events never loaded by COPY INTO and Auto Loader after a truncated file was corrected under the same name; 0 of 3,198 bad rows promoted when any failing data-quality check held the day |
| 0004 | [A managed platform, not a self-run lakehouse](0004-managed-platform.md) | Accepted | 909,968 rows recovered by snapshot rollback; 20 → 1 files merged per partition by optimize |
| 0005 | [Databricks or Snowflake: decided by a two-week proof of concept on fixed criteria](0005-databricks-or-snowflake.md) | Proposed | 11, 46, 3 models, data tests and unit tests that passed when the dbt project was built on Databricks after one change, with revenue figures identical to DuckDB's; 3 of 3 personal columns masked by one policy on the classification tag, including a column on a table created after the policy |
| 0006 | [Tables are kept in an open format, in storage the client owns](0006-open-format-in-the-clients-account.md) | Accepted | 909,968 rows recovered by snapshot rollback; 88 ms one-month predicate over 1.5M Iceberg rows |
| 0007 | [A Kimball star, with Type 2 history for every attribute facts are read against](0007-history-for-attributes-facts-read-against.md) | Accepted | 15.1% of a year's revenue on the wrong plan with a Type 1 account dimension; 5,048 of 5,048 invoices on the plan they billed, Type 2 dimension from dbt snapshots |
| 0008 | [Incremental models load their run's window and replace it by key](0008-incremental-by-interval.md) | Accepted | 96.56% of a month's events lost by high-water-mark loads backfilled newest day first, every run green; 0 of 89,508 events loaded by a data-interval incremental model on Airflow 3's default @daily, in 30 successful runs |
| 0009 | [Pipelines are scheduled by the platform's own jobs, not a separate orchestrator](0009-orchestration-on-the-platform.md) | Accepted | 0 of 89,508 events loaded by a data-interval incremental model on Airflow 3's default @daily, in 30 successful runs |
| 0010 | [Stage 2: customers' usage is served from a store fed by a stream, not from the platform](0010-customer-usage-serving.md) | Proposed | 6.1 s p99 from event time to queryable in ClickHouse at 1,000 events/s; 9 of 9 failure runs with every event layer exact |
| 0011 | [Classification tags drive masking and row filters; every table carries the account](0011-tags-drive-masking-and-row-filters.md) | Proposed | 3 of 3 personal columns masked by one policy on the classification tag, including a column on a table created after the policy; 1 of 5 accounts visible through a row filter keyed to the caller's identity |
| 0012 | [Erasure: delete by key, then let every copy of the old version expire inside 30 days](0012-erasure.md) | Proposed | 100 of 100 rows of an erased user still returned by time travel after DELETE and after REORG … APPLY (PURGE); refused time travel to the version before the delete, once the table's deleted-file retention had passed and VACUUM had run |
| 0013 | [Every source has a contract, checked in the producer's CI](0013-contracts-at-the-producer.md) | Accepted | 0 breaking schema changes passed as safe, in any mode; 2 of 51 changes flagged as breaking that are safe, per direction |
| 0014 | [Quality gates: tests on rows, checks on the day, reconciliation to billing](0014-quality-gates.md) | Accepted | 0 of 3,198 bad rows promoted when any failing data-quality check held the day; 4 of 4 deliberate model breaks that failed the build |
| 0015 | [Every analytical table can be restored to any point in the last 7 days](0015-restore-points.md) | Accepted | 365 of 365 days back after RESTORE TABLE, following an INSERT OVERWRITE of one day that left 1; 909,968 rows recovered by snapshot rollback |
<!-- decisions:end -->

Principles that hold across these decisions, rather than being one of them, are in
[principles](../docs/principles.md). The records of this repository's first version, a
reference architecture without a client, are in the
[v0.1.0 tag](https://github.com/technobasant/data-platform-architecture/tree/v0.1.0/decisions).

## Decisions inside the labs

The labs record their own, narrower decisions; the stage-2 and contract records here rest
on them.

| Repository | Decision records |
|---|---|
| [streaming-platform](https://github.com/technobasant/streaming-platform/tree/main/docs/adr) | 7: Kafka in KRaft mode, the transactional contract gate, Avro FULL_TRANSITIVE, end-to-end exactly-once, the Iceberg REST catalog, event-time deduplication and late data, the freshness SLO |
| [dataset-registry](https://github.com/technobasant/dataset-registry/tree/main/docs/adr) | 6: Go and sqlc, OpenLineage, JSON Schema validity sets, acknowledgement instead of blocking, freshness from the last write, tokens and open reads |
