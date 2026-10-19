# 0001. Analytics moves off the product's database onto a separate platform

- Status: Accepted
- Date: 2026-10-19
- Deciders: CTO, CFO, data lead; proposed by the architect
- Evidence: baseline_bi_on_primary, baseline_replica_long_reports, baseline_replica_feedback

## Context

Every report, dashboard and export reads the product's Postgres: the usage page from the
primary, the BI tool and the finance exports from its one read replica. The
[current state](../docs/02-current-state.md) measures what that costs. Reports on the
primary slow the product down. Reports on the replica are cancelled when the primary's
cleanup needs rows they are still reading, unless the replica holds the primary's cleanup
back instead, which bloats the product's busiest tables. Events are deleted after 90 days
because the table grew too large.

## Decision drivers

- Q1: reports must not slow the product.
- Q2: reports finish on the first attempt.
- Q4: 25 months of history, which is 760 million rows in a year and 3.8 billion in three.
- The product's database is not to be changed for analytics' sake.

## Options

| | Q1 product isolation | Q2 reports finish | Q4 history | Product database untouched |
|---|---|---|---|---|
| Keep everything on the primary | ✘ | ✔ | ✘ | ✔ |
| A dedicated reporting replica, cleanup conflicts tolerated | ✔ | ✘ long reports cancelled | ✘ | ✔ |
| The same replica with `hot_standby_feedback` on | ◐ the primary's cleanup waits for the longest report | ✔ | ✘ | ✘ its busiest tables bloat as reports grow |
| Partitioning and summary tables in Postgres | ◐ | ◐ | ◐ at much engineering cost | ✘ schema changes in the product's database |
| **A separate analytical platform fed by change data capture** | ✔ | ✔ | ✔ | ✔ one logical replication slot |

## Decision

Analytics moves to a separate platform, fed from the product's database by change data
capture ([0002](0002-cdc-from-the-product-database.md)). Until that platform serves the
dashboards, every BI query runs on the replica, never the primary, with the default conflict
settings: a cancelled report is a better failure than a slower product.

## Consequences

- The product's database loses its analytical load, and gains one replication slot to
  operate. A slot that is lost in an RDS failover, or that stalls and retains WAL, is the
  known risk of this design ([risks](../docs/risks.md)).
- Analysts get a second place where data lives, and numbers that are minutes to a day
  behind the product instead of current. The usage page keeps reading the primary until
  stage 2 gives it a serving path of its own.
- Reversible: the platform can be switched off and the reports pointed back at the replica.

## Revisit when

Never as a whole. The stopgap ends when the platform serves the BI tool, or after three
months, whichever is first.

## Evidence

<!-- evidence:start -->
- **93 → 794 ms** product p95 request latency, without and with the BI tool's reports on the primary. A lab copy of the client's database (Postgres 17, 2 vCPU and 4 GB, 31.5 million events); the product's request at 100 a second from pgbench; two analysts running the four BI queries in turn; five minutes per scenario after a checkpoint. Requests over 100 ms went from 4.8% to 23.0%. Source: [data-platform-architecture/results/baseline.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/baseline.json)
- **3 of 412** runs of the three long reports that finished on the read replica in five minutes; 409 were cancelled by recovery conflicts. The same lab, reports on a streaming replica with the default max_standby_streaming_delay of 30 s and hot_standby_feedback off, while the product updated users at 100 requests a second; analysts retried at once. Source: [data-platform-architecture/results/baseline.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/baseline.json)
- **20 of 20** runs of the long reports that finished on the replica with hot_standby_feedback on. The same lab and load; the cost, cleanup on the primary held back for as long as the longest report, was not visible in a five-minute window with reports of one to two minutes. Source: [data-platform-architecture/results/baseline.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/baseline.json)
<!-- evidence:end -->
