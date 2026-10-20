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
- Changes made and undone within a day must still be seen; no periodic extract catches them.
- The product's database is not to be loaded or changed for analytics.
- Managed first: no self-run Kafka in year one.

## Options

| | Q3 history complete | Deletes arrive | Load on the product database | Runs without new infrastructure |
|---|---|---|---|---|
| Nightly full extracts of each table | ◐ meets Q3 while plan changes are rarer than extracts: 13 monthly snapshots put 5,048 of 5,048 invoices on the right plan; ✘ only a change made and undone between two extracts | ✘ inferred by absence | ◐ a full scan a night | ✔ |
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

Periodic extracts alone could meet Q3, since plan changes are rarer than an extract cycle.
What decides CDC is the rest: deletes (Q10, an erased user must reach the platform, and the
product's own 90-day purge of `events` must not), changes made and undone within a day,
which no extract ever sees, and reading the write-ahead log instead of scanning the primary.

`rds.logical_replication` is a static parameter: turning it on takes one restart of the
primary, in a maintenance window agreed with the product team. After that one restart, the
only ongoing new thing the primary carries is the logical replication slot.

### Deletes, by table

CDC carries every delete, but not every delete is erasure, and the platform treats them
differently by table:

| Table | What a delete means | What the platform does |
|---|---|---|
| `events` | the product's nightly 90-day purge, about 350,000 DELETEs a day; this is the product's retention, not a business delete | ignored: the platform keeps its own 25 months of history regardless of what the product has purged |
| `users`, `accounts` | a business event: an account closes a user's row, or a person is erased | applied: the Type 2 row is closed, and personal columns are erased by the erasure job, keyed by user ([0012](0012-erasure.md)), not by the CDC delete itself |

A check holds the line between the two: per-day event counts, for days the product has
already purged, must not fall ([9. Operations](../docs/09-operations.md)).

### What the publication captures

`users.last_seen_at` changes on every request. A full-row publication would copy each
user's `email` and `full_name` into `raw` on every such change, kept for 25 months: the
busiest column in the table turning the two most sensitive ones into the platform's
highest-churn data. The publication excludes `last_seen_at` with a column list, which
needs PostgreSQL 15 or later. [The brief](../docs/01-brief.md) does not state the
primary's engine version; confirming it, and upgrading first if the instance predates 15,
is a prerequisite of wave 1.

## Consequences

- History is complete from the day capture starts. Before that day, only what the extracts
  and the Stripe export show is known, and the first version of each account is stretched
  back to its signup, as the dbt project does. Events are the exception: the nightly CSV
  exports in S3 are backfilled into raw in wave 1, so Q4 is met for the period the exports
  cover ([8. Migration](../docs/08-migration.md)).
- One logical replication slot on RDS, enabled by the one planned restart above: it must be
  monitored for retained WAL and recreated after a major-version upgrade or failover
  ([9. Operations](../docs/09-operations.md)).
- Schema changes in the product reach the platform as change events and are checked
  against the contract before anything reads them
  ([0013](0013-contracts-at-the-producer.md)).

## Revisit when

The chosen platform's own connector reaches general availability (Databricks), or the
product team adopts an outbox or event stream that already carries the same changes.

## Evidence

<!-- evidence:start -->
- **533 of 570** account changes in a year seen by monthly snapshots. A change counts as seen if a snapshot version starts at its exact updated_at; signups excluded. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **15.1%** of a year's revenue on the wrong plan with a Type 1 account dimension. 5,048 generated invoices (seed 7, Oct 2025 – Sep 2026) attributed by each account's current plan and compared with the plan the generator billed; $152,227 of $1,010,202. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **5,048 of 5,048** invoices on the plan they billed, Type 2 dimension from dbt snapshots. As-of join of each invoice to the dim_account version in effect at billing, scored against the generator's truth file; the dimension was built from 13 monthly snapshot loads. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
