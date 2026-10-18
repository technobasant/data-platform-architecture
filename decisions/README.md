# Decisions

Platform-level decisions for the reference architecture, one file each: context, decision, consequences, alternatives, and the measured evidence (generated from [`../evidence/evidence.yml`](../evidence/evidence.yml) by `scripts/build.py`).

<!-- decisions:start -->
| # | Decision | Status | Backed by |
|---|---|---|---|
| 0001 | [Three ways in: events through Kafka, database changes through CDC, vendor exports as files](0001-three-ways-in.md) | Accepted | 9 of 9 failure runs with every event layer exact; 533 of 570 account changes in a year seen by monthly snapshots |
| 0002 | [Iceberg tables on object storage, behind a catalog that vends scoped credentials](0002-open-tables-scoped-credentials.md) | Accepted | 909,968 rows recovered by snapshot rollback; 20 → 1 files merged per partition by optimize |
| 0003 | [Exactly-once by transactions upstream, idempotence at the edge, and counts reconciled per layer](0003-exactly-once.md) | Accepted | 9 of 9 failure runs with every event layer exact; 59.8% of on-time events left in the window counts after one broker kill |
| 0004 | [Contracts at every producer boundary; breaking changes wait for their consumers](0004-contracts-with-acknowledgement.md) | Accepted | 0 breaking schema changes passed as safe, in any mode; 2 of 51 changes flagged as breaking that are safe, per direction |
| 0005 | [Keep history for every attribute that facts are read against](0005-history-for-attributes-facts-read-against.md) | Accepted | 15.1% of a year's revenue on the wrong plan with a Type 1 account dimension; 5,048 of 5,048 invoices on the plan they billed, Type 2 dimension from dbt snapshots |
| 0006 | [Incremental loads take the run's data interval and replace by key; schedules name their timetable](0006-incremental-by-interval.md) | Accepted | 96.56% of a month's events lost by high-water-mark loads backfilled newest day first, every run green; 0 of 89,508 events loaded by a data-interval incremental model on Airflow 3's default @daily, in 30 successful runs |
| 0007 | [Freshness is an SLO measured from the consumer's side and alerted on burn rate](0007-freshness-slo-from-the-consumer.md) | Accepted | 6.1 s p99 from event time to queryable in ClickHouse at 1,000 events/s; 59–62 s from a frozen pipeline to a firing burn-rate alert |
| 0008 | [Serve by access pattern: a real-time OLAP store, distributed Postgres, and the lakehouse](0008-serve-by-access-pattern.md) | Accepted | 6.1 s p99 from event time to queryable in ClickHouse at 1,000 events/s; 4.2× faster join co-located than repartitioned |
| 0009 | [Every stateful store has a rehearsed failover and restore with measured times](0009-rehearsed-recovery.md) | Accepted | 8 of 8 failover scenarios passed; 10–20 s observed promotion window after SIGKILL |
| 0010 | [Three layers of tests: logic on written rows, data on real rows, and breaks to prove both](0010-three-layers-of-tests.md) | Accepted | 4 of 4 deliberate model breaks that failed the build; 5,048 of 5,048 invoices on the plan they billed, Type 2 dimension from dbt snapshots |
| 0011 | [Features for models are served point-in-time correct, from one definition online and offline](0011-point-in-time-features.md) | Accepted | 0.363 vs 0.941 future AUC-PR, naive join against point-in-time join; 99.905% of 9,500 live requests served exactly the training features |
| 0012 | [Platform services ship by canary, judged against the stable version](0012-canary-releases.md) | Accepted | 6 of 6 bad releases aborted by canary analysis; 0 of 18,003 requests failed across three good canary releases |
| 0013 | [A managed warehouse or lakehouse platform is chosen per workload, with the cost model and the team in view](0013-managed-platform-per-workload.md) | Proposed | modelled, not yet measured |
<!-- decisions:end -->

## Decisions inside the labs

The labs record their own, narrower decisions. Each platform decision above links to the ones it rests on.

| Repository | Decision records |
|---|---|
| [streaming-platform](https://github.com/technobasant/streaming-platform/tree/main/docs/adr) | 7: Kafka in KRaft mode, the transactional contract gate, Avro FULL_TRANSITIVE, end-to-end exactly-once, the Iceberg REST catalog, event-time deduplication and late data, the freshness SLO |
| [dataset-registry](https://github.com/technobasant/dataset-registry/tree/main/docs/adr) | 6: Go and sqlc, OpenLineage, JSON Schema validity sets, acknowledgement instead of blocking, freshness from the last write, tokens and open reads |
| [realtime-ml](https://github.com/technobasant/realtime-ml/tree/main/docs/adr) | 7: Feast with DuckDB and Redis, two implementations per feature, window semantics, label maturity, the promotion gate, Kafka KRaft, drift monitoring |
| [platform-deployments](https://github.com/technobasant/platform-deployments/tree/main/docs/adr) | 8: Argo CD app of apps, the Rollouts canary, the Envoy sidecar, CloudNativePG, Kyverno, kind, static Terraform, in-cluster Git |
| [governed-agent](https://github.com/technobasant/governed-agent/tree/main/docs/adr) | 6: the explicit graph, MCP as the boundary, the grounding check, review before execute, the outbox, the replayed model in CI |
| [retrieval-bench](https://github.com/technobasant/retrieval-bench/tree/main/docs/adr) | 5: embed once, iso-recall comparison, latency measurement, datasets, Postgres full text |
| [evalproof](https://github.com/technobasant/evalproof/tree/main/docs/adr) | 3: the judge as a classifier, local-first providers, gating on significance |
