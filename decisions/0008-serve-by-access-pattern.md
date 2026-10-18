# 0008. Serve by access pattern: a real-time OLAP store, distributed Postgres, and the lakehouse

- Status: Accepted
- Date: 2026-10-18
- Evidence: stream_freshness_p99, ddb_colocation_join, ddb_rebalance_errors, ddb_skew_spread, ddb_ch_replica_outage

## Context

Three kinds of reader want the same data differently. Customers want their own usage, fresh, in milliseconds. The product's own features want transactional reads and writes per tenant. Analysts want anything joined to anything, and can wait seconds.

## Decision

- **Customer-facing aggregates:** ClickHouse, replicated, with the tenant first in every sort key, fed from the event stream.
- **Multi-tenant transactional data:** PostgreSQL, distributed by tenant with Citus once one node is not enough; every tenant table co-located with `tenants`.
- **Analysis:** the lakehouse ([0002](0002-open-tables-scoped-credentials.md)) through a SQL engine, or a managed warehouse reading the same tables ([0013](0013-managed-platform-per-workload.md)).

## Consequences

- Events were queryable in ClickHouse at p99 6.1 s after they happened, and with one replica down, 40 of 40 inserts still succeeded.
- Co-location is the performance model: the same join ran 4.2× faster co-located than repartitioned.
- Scale-out is an operation, not a migration: a worker joined under load with 0 errors.
- Tenant skew needs splitting, not moving: isolating the largest tenant took node sizes from 2.36× apart to 1.10×.
- Three stores to operate, each with its own recovery ([0009](0009-rehearsed-recovery.md)).

## Alternatives considered

- **One warehouse for everything.** Simplest; customer-facing latency and per-query cost are where it breaks first.
- **One OLTP database for everything.** Analytical scans compete with product traffic.

## Evidence

<!-- evidence:start -->
- **6.1 s** p99 from event time to queryable in ClickHouse at 1,000 events/s. ClickHouse ingest time minus event time for every on-time event, median of three 90 s runs; the floor is the 5 s checkpoint interval at which Flink's transactions commit. Source: [streaming-platform/MEASUREMENTS.md](https://github.com/technobasant/streaming-platform/blob/main/MEASUREMENTS.md)
- **4.2×** faster join co-located than repartitioned. The same join over tenants 1–400, both returning 617,895 rows; p50 of 7 runs, 1,251.7 ms co-located on (tenant_id, user_id) vs 5,206.0 ms against a copy distributed by user_id. Source: [distributed-db-lab/MEASUREMENTS.md](https://github.com/technobasant/distributed-db-lab/blob/main/MEASUREMENTS.md)
- **0 errors** while a worker joined and 7 shard groups moved under load. 8 client threads for 600 s, 80% one-tenant reads and 20% single-row inserts against the Citus coordinator; every acknowledged write counted back afterwards. Source: [distributed-db-lab/MEASUREMENTS.md](https://github.com/technobasant/distributed-db-lab/blob/main/MEASUREMENTS.md)
- **2.36× → 1.10×** spread between the largest and smallest worker. Node bytes after the default by_disk_size rebalance, then after isolating the largest tenant to its own shard and rebalancing with citus.rebalancer_by_disk_size_base_cost set to 0. Source: [distributed-db-lab/MEASUREMENTS.md](https://github.com/technobasant/distributed-db-lab/blob/main/MEASUREMENTS.md)
- **40 of 40** inserts succeeded with a ClickHouse replica down. One replica of a 2-shard × 2-replica ReplicatedMergeTree cluster killed for 60.3 s while inserts and reads ran through the Distributed table. Source: [distributed-db-lab/MEASUREMENTS.md](https://github.com/technobasant/distributed-db-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- distributed-db-lab [README: what it shows](https://github.com/technobasant/distributed-db-lab#what-it-shows)
