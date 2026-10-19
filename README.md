# data-platform-architecture

A data architecture engagement for a fictional B2B SaaS company that has outgrown running its
analytics on the product's Postgres: the brief, the current state measured, the options, a
staged target architecture, the data model and contracts, security and governance, the
migration, and the decisions, each backed by measured results.

[![ci](https://github.com/technobasant/data-platform-architecture/actions/workflows/ci.yml/badge.svg)](https://github.com/technobasant/data-platform-architecture/actions/workflows/ci.yml)

## Executive summary

**The client.** 6,000 customer accounts, 350,000 product events a day growing threefold a
year, a data team of two, and everything the business knows about itself read from the
product's Postgres on RDS and its one read replica ([the brief](docs/01-brief.md)).

**What is wrong, measured** on a lab copy of its database ([current state](docs/02-current-state.md)):

- With the BI tool's reports on the primary, the product's 95th-percentile request went
  from **93 ms to 794 ms**.
- On the replica, **3 of 412** runs of the long reports finished in five minutes; the rest
  were cancelled by recovery conflicts. Turning on `hot_standby_feedback` lets them finish by
  holding back the product database's cleanup for as long as the longest report runs.
- Revenue by plan is read from each account's *current* plan; on this business's shape of
  data that puts **15.1%** of a year's revenue on the wrong plan.
- Events are deleted after 90 days, nobody can say who read personal data, and there is no
  way to erase a person from every copy, which two enterprise prospects require.

**The recommendation.**

1. Now: every report on the replica, never the primary. A cancelled report is a better
   failure than a slower product ([0001](decisions/0001-analytics-off-the-product-database.md)).
2. Within four months: a managed analytical platform fed by change data capture, with a
   Type 2 star schema reconciled to Stripe, governance by classification tags, and erasure
   that can be proven ([stage 1](docs/05-target-architecture.md#the-stages)).
3. **Databricks or Snowflake is decided by a two-week proof of concept** on criteria and
   weights fixed in advance ([0005](decisions/0005-databricks-or-snowflake.md)). At this
   scale the list-price bill does not separate them, from about $370 to $770 a month today
   and $1,500 to $3,100 at 36 months; the people to run a self-built lakehouse would cost
   more than either ([options](docs/04-options.md)).
4. Months 5–9: customers' usage under a minute old from a store fed by a stream (stage 2).
   Months 9–12: the assistant, on the same governed tables
   ([AI architecture](https://github.com/technobasant/ai-platform-architecture)).

## Contents

| | Document | What it answers |
|---|---|---|
| 1 | [Brief](docs/01-brief.md) | who the client is, why now, stakeholders, constraints, scale |
| 2 | [Current state](docs/02-current-state.md) | what running analytics on the product's database costs, measured |
| 3 | [Requirements](docs/03-requirements.md) | each consumer's needs; 15 quality targets as testable scenarios |
| 4 | [Options](docs/04-options.md) | five options against the requirements; cost with and without people |
| 5 | [Target architecture](docs/05-target-architecture.md) | the stages, C4 context and containers, zones, deployment, failure modes |
| 6 | [Data model](docs/06-data-model.md) | the star schema, bus matrix, keys and history; [contracts](models/contracts) |
| 7 | [Security and governance](docs/07-security-and-governance.md) | classification, roles, row filters, erasure, SOC 2 and GDPR controls |
| 8 | [Migration](docs/08-migration.md) | inventory, waves, running both, cutover and rollback |
| 9 | [Operations](docs/09-operations.md) | what is watched, runbooks, change and release |
| 10 | [Roadmap](docs/10-roadmap.md) | the first 90 days and the year, with costs and team |
| | [Decisions](decisions) | 15 decision records with options, drivers and evidence |
| | [Risks](docs/risks.md), [principles](docs/principles.md) | the register; the rules across decisions |

## Decisions

<!-- decisions:start -->
| # | Decision | Status | Backed by |
|---|---|---|---|
| 0001 | [Analytics moves off the product's database onto a separate platform](decisions/0001-analytics-off-the-product-database.md) | Accepted | 93 → 794 ms product p95 request latency, without and with the BI tool's reports on the primary; 3 of 412 runs of the three long reports that finished on the read replica in five minutes; 409 were cancelled by recovery conflicts |
| 0002 | [The product's tables reach the platform by change data capture, not extracts](decisions/0002-cdc-from-the-product-database.md) | Accepted | 533 of 570 account changes in a year seen by monthly snapshots; 15.1% of a year's revenue on the wrong plan with a Type 1 account dimension |
| 0003 | [Files that land are immutable, and every load writes by key](decisions/0003-files-immutable-loads-by-key.md) | Accepted | 1,638 events never loaded by COPY INTO and Auto Loader after a truncated file was corrected under the same name; 0 of 3,198 bad rows promoted when any failing data-quality check held the day |
| 0004 | [A managed platform, not a self-run lakehouse](decisions/0004-managed-platform.md) | Accepted | 909,968 rows recovered by snapshot rollback; 20 → 1 files merged per partition by optimize |
| 0005 | [Databricks or Snowflake: decided by a two-week proof of concept on fixed criteria](decisions/0005-databricks-or-snowflake.md) | Proposed | modelled, not yet measured |
| 0006 | [Tables are kept in an open format, in storage the client owns](decisions/0006-open-format-in-the-clients-account.md) | Accepted | 909,968 rows recovered by snapshot rollback; 88 ms one-month predicate over 1.5M Iceberg rows |
| 0007 | [A Kimball star, with Type 2 history for every attribute facts are read against](decisions/0007-history-for-attributes-facts-read-against.md) | Accepted | 15.1% of a year's revenue on the wrong plan with a Type 1 account dimension; 5,048 of 5,048 invoices on the plan they billed, Type 2 dimension from dbt snapshots |
| 0008 | [Incremental models load their run's window and replace it by key](decisions/0008-incremental-by-interval.md) | Accepted | 96.56% of a month's events lost by high-water-mark loads backfilled newest day first, every run green; 0 of 89,508 events loaded by a data-interval incremental model on Airflow 3's default @daily, in 30 successful runs |
| 0009 | [Pipelines are scheduled by the platform's own jobs, not a separate orchestrator](decisions/0009-orchestration-on-the-platform.md) | Accepted | 0 of 89,508 events loaded by a data-interval incremental model on Airflow 3's default @daily, in 30 successful runs |
| 0010 | [Stage 2: customers' usage is served from a store fed by a stream, not from the platform](decisions/0010-customer-usage-serving.md) | Proposed | 6.1 s p99 from event time to queryable in ClickHouse at 1,000 events/s; 9 of 9 failure runs with every event layer exact |
| 0011 | [Classification tags drive masking and row filters; every table carries the account](decisions/0011-tags-drive-masking-and-row-filters.md) | Proposed | modelled, not yet measured |
| 0012 | [Erasure: delete by key, then let every copy of the old version expire inside 30 days](decisions/0012-erasure.md) | Proposed | modelled, not yet measured |
| 0013 | [Every source has a contract, checked in the producer's CI](decisions/0013-contracts-at-the-producer.md) | Accepted | 0 breaking schema changes passed as safe, in any mode; 2 of 51 changes flagged as breaking that are safe, per direction |
| 0014 | [Quality gates: tests on rows, checks on the day, reconciliation to billing](decisions/0014-quality-gates.md) | Accepted | 0 of 3,198 bad rows promoted when any failing data-quality check held the day; 4 of 4 deliberate model breaks that failed the build |
| 0015 | [Every analytical table can be restored to any point in the last 7 days](decisions/0015-restore-points.md) | Accepted | 365 of 365 days back after RESTORE TABLE, following an INSERT OVERWRITE of one day that left 1; 909,968 rows recovered by snapshot rollback |
<!-- decisions:end -->

Every figure, with its method and source file, is in [EVIDENCE.md](EVIDENCE.md).

## What is measured and what is not

| | Status |
|---|---|
| The current state | measured: [`baseline/`](baseline) runs the client's database and workload in Docker, four scenarios ([`results/baseline.json`](results/baseline.json)) |
| Loading, history, backfills, quality gates, overwrite and restore on Delta | measured in [data-stack-lab](https://github.com/technobasant/data-stack-lab), on the same synthetic business, partly on Databricks |
| Contracts | linted in CI; a breaking change is shown to fail the producer-side check |
| Platform cost | modelled from list prices with stated assumptions ([`cost/`](cost)); the proof of concept measures it |
| Databricks against Snowflake, governance and erasure on each | designed, with criteria fixed; measured in the proof of concept |
| Stage 2 and the assistant | designed; decided when each stage starts |

The client is fictional and its data synthetic. Nothing here describes a real company's
platform. `python scripts/build.py --check` keeps every decision's evidence, the decision
tables and the cost tables identical to their sources, and CI checks every link.

## Licence

Apache-2.0. See [LICENSE](LICENSE).
