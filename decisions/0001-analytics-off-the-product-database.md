# 0001. Analytics moves off the product's database onto a separate platform

- Status: Accepted
- Date: 2026-10-19
- Deciders: CTO, CFO, data lead; proposed by the architect
- Evidence: baseline_bi_on_primary, baseline_replica_long_reports, baseline_replica_feedback, baseline_replica_delay

## Context

Every report, dashboard and export reads the product's Postgres: the usage page from the
primary, the BI tool and the finance exports from its one read replica. The
[current state](../docs/02-current-state.md) measures what that costs. Reports on the
primary slow the product down. Reports on the replica are cancelled when the primary's
cleanup needs rows they are still reading, unless the replica holds the primary's cleanup
back instead, which bloats the product's busiest tables, or is allowed to fall behind. Events
are deleted after 90 days because the table grew too large.

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
| A replica for reports alone, `max_standby_streaming_delay` at 15 minutes, feedback off | ✔ | ◐ reports up to 15 minutes; the replica falls minutes behind | ✘ | ✔ a parameter group for the replica |
| Partitioning and summary tables in Postgres | ◐ | ◐ | ◐ at much engineering cost | ✘ schema changes in the product's database |
| **A separate analytical platform fed by change data capture** | ✔ | ✔ | ✔ | ✔ one logical replication slot |

## Decision

Analytics moves to a separate platform, fed from the product's database by change data
capture ([0002](0002-cdc-from-the-product-database.md)). Until that platform serves the
dashboards, every BI query runs on the replica, never the primary, and the replica becomes
the reports' alone: `max_standby_streaming_delay` raised to 15 minutes in its own parameter
group, `hot_standby_feedback` off. In the lab at the brief's peak rate every report finished
and the replica fell up to 4.7 minutes behind, which costs nothing: the product reads only the
primary, and the reports need yesterday. A report that runs longer than 15 minutes is still
cancelled; that is a better failure than a slower product or a bloated one.

## Consequences

- The product's database loses its analytical load, and gains one replication slot to
  operate. A slot that is lost in an RDS failover, or that stalls and retains WAL, is the
  known risk of this design ([risks](../docs/risks.md)).
- Until the platform exists, the replica runs minutes behind the primary whenever a long
  report is open; nothing the product serves reads it. If anything ever needs the replica to
  be current, it gets a replica of its own.
- Analysts get a second place where data lives, and numbers that are minutes to a day
  behind the product instead of current. The usage page keeps reading the primary until
  stage 2 gives it a serving path of its own.
- Reversible: the platform can be switched off and the reports pointed back at the replica.

## Revisit when

Never as a whole. The stopgap ends when the platform serves the BI tool, or after three
months, whichever is first.

## Evidence

<!-- evidence:start -->
- **40 → 525 ms** product p95 request latency, without and with the BI tool's reports on the primary. A lab copy of the client's database (Postgres 17, 2 vCPU and 4 GB, 31.5 million events); the product's request at 12 a second from pgbench, the brief's weekday peak (each request records one event; 350,000 a day average 4 a second); two analysts running the four BI queries in turn; five minutes per scenario after a checkpoint. Requests over 100 ms went from 2.2% to 24.0%; at a stress rate of 100 a second, p95 went from 93 to 794 ms. Source: [data-platform-architecture/results/baseline-brief-rate.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/baseline-brief-rate.json)
- **3 of 35** runs of the three long reports that finished on the read replica in five minutes; 32 were cancelled by recovery conflicts. The same lab at the brief's peak rate, reports on a streaming replica with the default max_standby_streaming_delay of 30 s and hot_standby_feedback off, while the product updated users; analysts retried at once. At a stress rate of 100 requests a second it was 3 of 412. Source: [data-platform-architecture/results/baseline-brief-rate.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/baseline-brief-rate.json)
- **11 of 11** report runs that finished on the replica with hot_standby_feedback on, while cleanup of the product's users table was held back. The same lab and load; in five minutes the users table's dead rows on the primary rose from 3,111 to 3,630, cleanup held back for as long as the longest report ran. Source: [data-platform-architecture/results/baseline-brief-rate.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/baseline-brief-rate.json)
- **7 of 7** report runs that finished on a replica for reports alone, with max_standby_streaming_delay at 15 minutes and feedback off; it fell up to 4.7 minutes behind. The same lab and load; replay waited for the reports instead of cancelling them, the primary's cleanup was not held back (users dead rows fell from 3,630 to 3,206 as autovacuum ran), and the replica's replay lag reached 281.7 s (142.1 s median). Source: [data-platform-architecture/results/baseline-brief-rate.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/baseline-brief-rate.json)
<!-- evidence:end -->
