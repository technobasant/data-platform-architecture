# 0010. Stage 2: customers' usage is served from a store fed by a stream, not from the platform

- Status: Proposed
- Date: 2026-10-19
- Deciders: CTO, VP Product; proposed by the architect
- Evidence: stream_freshness_p99, stream_failure_exactness, stream_window_undercount

## Context

Enterprise customers want their usage page under a minute old (Q12), and the page must
never show another account's data (Q11). Today it reads the product's primary, which is
current and is one of the loads [0001](0001-analytics-off-the-product-database.md) moves
away. A batch analytical platform is minutes to a day behind, and its warehouses are sized
for analysts, not for thousands of small queries from the product.

The real driver is growth, not today's traffic. At 36 months the product's `events` table
holds about 450 million rows for its own 90 days (5 million a day); customers ask for usage
beyond 90 days, which the primary does not keep at all. Reading the primary meets Q12 today
([3. Requirements](../docs/03-requirements.md)), and stops being able to answer the question
the moment a customer asks about day 91. Stage 3's assistant needs the same per-account
query path the usage page does
([AI architecture](https://github.com/technobasant/ai-platform-architecture)), so the store
built here is not only for the usage page.

## Decision drivers

- Q12: under 60 s, p99.
- Q11: tenant isolation on every path.
- Q1: the product's database is not the analytics store.
- Growth: the primary keeps only 90 days, and usage beyond that is asked for already.
- Cost per query at the product's request rate.
- Stage 3: the assistant needs the same per-account query path.

## Options

| | Q12 freshness | Q11 isolation | Cost at product request rates | Systems to run |
|---|---|---|---|---|
| Keep reading the primary | ✔ today; ✘ at 36 months, once a customer asks past the primary's own 90 days | ◐ application code | ✔ | ✔ |
| Query the analytical platform from the product | ✘ minutes behind | ◐ row filters | ✘ a warehouse awake all day: $2,657 a month at the smallest size in the client's region, 4 DBU an hour measured in the proof of concept at $0.91 a DBU | ✔ |
| Pre-computed per-account tables pushed back to Postgres | ✘ batch | ✔ | ✔ | ◐ |
| **Events streamed into a real-time OLAP store keyed by account** (managed ClickHouse, or the platform's own low-latency option) | ✔ | ✔ account first in every key | ✔ | ✘ a stream and a store |

## Decision

Proposed for stage 2, to be decided when stage 2 starts: product events go to a managed
stream, and from it, exactly once, into a real-time OLAP store with the account as the
leading key, which the usage page reads. The analytical platform keeps the history and
reconciles the store's counts daily. Until then the usage page reads the primary.

## Consequences

- Two more systems, both managed: a stream and a store. They are justified only by Q12,
  which is why this is stage 2 and not stage 1.
- Windowed counts in a stream undercount when partitions are replayed out of order; the
  store keeps records and computes counts at read time, and the daily reconciliation
  catches drift.
- Isolation tests run against the store's query path as well as the platform's.

## Revisit when

Stage 2 starts: decide with the platform chosen in
[0005](0005-databricks-or-snowflake.md) known, since either may offer a fast enough path of
its own by then.

## Evidence

<!-- evidence:start -->
- **6.1 s** p99 from event time to queryable in ClickHouse at 1,000 events/s. ClickHouse ingest time minus event time for every on-time event, median of three 90 s runs; the floor is the 5 s checkpoint interval at which Flink's transactions commit. Source: [streaming-platform/MEASUREMENTS.md](https://github.com/technobasant/streaming-platform/blob/main/MEASUREMENTS.md)
- **9 of 9** failure runs with every event layer exact. Three controller-broker kills, three TaskManager kills and three 150 s stalls under load; Kafka, ClickHouse, Iceberg and the dead-letter topic reconciled against the generator's ledger by sequence number. Source: [streaming-platform/MEASUREMENTS.md](https://github.com/technobasant/streaming-platform/blob/main/MEASUREMENTS.md)
- **59.8%** of on-time events left in the window counts after one broker kill. 118,229 of 197,749 on-time events counted in their 10 s windows in the worst of three broker-kill runs; the rest went to the late side output because catch-up reordered partitions past the 5 s watermark bound. Source: [streaming-platform/MEASUREMENTS.md](https://github.com/technobasant/streaming-platform/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
