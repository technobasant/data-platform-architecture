# 0002. The product's tables reach the platform by change data capture, not extracts

- Status: Accepted
- Date: 2026-10-19
- Deciders: CTO, data lead; proposed by the architect
- Evidence: dsl_snapshot_coverage, dsl_type1_misattributed, dsl_type2_correct

## Context

Accounts, users and plans live in the product's Postgres and are updated in place. The
plan an account was on when an invoice was billed exists nowhere once the account changes
plan, which is why revenue by plan disagrees with billing. Any copy taken on a schedule
sees only the state at that moment; a change made and undone between two copies is never
seen.

## Decision drivers

- Q3: every invoice on the plan it billed, reconciled to Stripe.
- Q10: deletes in the product (an erased user) must reach the platform.
- The product's database is not to be loaded or changed for analytics.
- Managed first: no self-run Kafka in year one.

## Options

| | Q3 history complete | Deletes arrive | Load on the product database | Runs without new infrastructure |
|---|---|---|---|---|
| Nightly full extracts of each table | ✘ changes between extracts lost | ✘ inferred by absence | ◐ a full scan a night | ✔ |
| Incremental extracts on `updated_at` | ✘ same | ✘ | ✔ | ✔ |
| **CDC from the write-ahead log, managed** (Openflow, Lakeflow Connect, or AWS DMS) | ✔ every change | ✔ | ✔ reads the log | ✔ |
| CDC with Debezium and Kafka, self-run | ✔ | ✔ | ✔ | ✘ a Kafka cluster to run |

## Decision

The product's tables are captured from the write-ahead log by a managed CDC service into
the platform's raw layer, keeping every change with its log position. Which service follows
from the platform choice ([0005](0005-databricks-or-snowflake.md)): Snowflake's Openflow
PostgreSQL connector is generally available; Databricks' Lakeflow Connect PostgreSQL
connector is in Public Preview, so on Databricks AWS DMS is the default until it is
generally available. Type 2 history is built from the change rows
([0007](0007-history-for-attributes-facts-read-against.md)).

## Consequences

- History is complete from the day capture starts. Before that day, only what the extracts
  and the Stripe export show is known, and the first version of each account is stretched
  back to its signup, as the dbt project does.
- One logical replication slot on RDS: it must be monitored for retained WAL and recreated
  after a major-version upgrade or failover ([9. Operations](../docs/09-operations.md)).
- Schema changes in the product reach the platform as change events and are checked
  against the contract before anything reads them
  ([0013](0013-contracts-at-the-producer.md)).

## Revisit when

The chosen platform's own connector reaches general availability (Databricks), or the
product team adopts an outbox or event stream that already carries the same changes.

## Evidence

<!-- evidence:start -->
- **533 of 570** account changes in a year seen by monthly snapshots. A change counts as seen if a snapshot version starts at its exact updated_at; signups excluded. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **15.1%** of a year's revenue on the wrong plan with a Type 1 account dimension. 5,048 synthetic invoices (seed 7, Oct 2025 – Sep 2026) attributed by each account's current plan and compared with the plan the generator billed; $152,227 of $1,010,202. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **5,048 of 5,048** invoices on the plan they billed, Type 2 dimension from dbt snapshots. As-of join of each invoice to the dim_account version in effect at billing, scored against the generator's truth file; the dimension was built from 13 monthly snapshot loads. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
