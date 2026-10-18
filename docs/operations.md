# Operations

Runbooks for the events that happen every month on a data platform. Each says what triggers it, what to do, how to know it worked, and where it was rehearsed.

## Backfill a range of days

- **When:** a model changed, or a source re-delivered history.
- **Do:** run the DAG for each day's data interval with `airflow backfill create`. Order does not matter for interval loads ([0006](../decisions/0006-incremental-by-interval.md)); prefer `--max-active-runs` within the warehouse's capacity.
- **Verify:** per-day row counts against the landing files; no day doubled.
- **Rehearsed:** [data-stack-lab, Airflow project](https://github.com/technobasant/data-stack-lab/tree/main/airflow): four orders, interval loads lost nothing.
- **Never:** backfill a model that uses a high-water mark without a full refresh afterwards. Newest-first, two such models lost 96.56% of a month with every run green.

## A day's input arrives late

- **Signal:** the day's run fails at the load step (it fails without retries on missing input).
- **Do:** when the file lands, clear and re-run that day.
- **Verify:** the day's freshness check turns green; counts match the file.

## A producer wants a breaking schema change

- **Signal:** the contract check fails in the producer's CI.
- **Do:** open a change request in the registry; it lists the consumers to ask. Ship when all acknowledge, or ship a compatible change instead.
- **Rehearsed:** [dataset-registry](https://github.com/technobasant/dataset-registry).

## A stream stalls or a broker dies

- **Signal:** freshness burn-rate page; consumer lag.
- **Do:** restart the job from its last checkpoint; replace the broker. Recompute affected window aggregates from the record layer.
- **Verify:** per-layer reconciliation is exact; window counts match the recomputation.
- **Rehearsed:** [streaming-platform](https://github.com/technobasant/streaming-platform): broker and worker kills, a stall.

## Postgres primary fails

- **Signal:** Patroni leader change.
- **Do:** nothing, if promotion completes; confirm the old primary rejoined with `pg_rewind`. Check CDC replication slots exist on the new primary before declaring recovery.
- **Verify:** writes succeed; replication lag back to zero; slot positions advancing.
- **Rehearsed:** [postgres-ha-lab](https://github.com/technobasant/postgres-ha-lab): promotion in 10–20 s. CDC slots across failover are not yet rehearsed.

## Restore after a bad write

- **Lakehouse table:** roll back to the last good snapshot, then re-run the jobs after it. Rehearsed in [lakehouse-lab](https://github.com/technobasant/lakehouse-lab): 909,968 rows restored.
- **Postgres:** point-in-time restore to before the mistake, on a separate instance; copy the rows back. Rehearsed in [postgres-ha-lab](https://github.com/technobasant/postgres-ha-lab): a dropped table's 5 of 5 rows restored.

## One tenant outgrows its node

- **Signal:** node size spread on the Citus cluster.
- **Do:** isolate the tenant to its own shard, then rebalance by size with the base cost at 0. Add a worker under load if needed.
- **Rehearsed:** [distributed-db-lab](https://github.com/technobasant/distributed-db-lab): spread 2.36× → 1.10×; a worker joined with 0 errors.

## Upgrading Airflow or dbt

- **Airflow 3:** cron strings now mean trigger timetables with no data interval. Before upgrading, set `CronDataIntervalTimetable` on every DAG that loads by interval, and run the tests that assert each run's window.
- **dbt v2:** run the project's unit tests and deliberate breaks on v2 before switching. 2.0.8 does not compare expected timestamps in unit tests (dbt-labs/dbt#15894).
