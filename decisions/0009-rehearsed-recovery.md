# 0009. Every stateful store has a rehearsed failover and restore with measured times

- Status: Accepted
- Date: 2026-10-18
- Evidence: lab_scenarios, lab_patroni_promotion, lab_replica_rebuild, lab_pitr_recovery, lakehouse_rollback

## Context

A recovery procedure that has never been run is a hypothesis. Each store fails differently: a primary dies, a replica falls behind, an operator deletes the wrong rows, a table is overwritten.

## Decision

- Each stateful store (Postgres, the OLAP store, Kafka, the catalog, the lakehouse) has a written failover and restore procedure, a recovery-time and recovery-point objective, and a drill that measures both.
- Postgres runs with an HA manager (Patroni) and point-in-time recovery from an off-host backup repository with TLS.
- Lakehouse tables keep snapshots for longer than the time to detect a bad write ([0002](0002-open-tables-scoped-credentials.md)).
- Drills are repeated after every major version upgrade, because failure behaviour changes between versions.

## Consequences

- Eight of eight failover scenarios passed across six engines.
- A Patroni leader killed with SIGKILL was replaced in 10–20 s; a replica was rebuilt from backup in about 5 s; a point-in-time restore of a dropped table brought back all 5 of its rows.
- A table rollback restored 909,968 rows.
- Drills cost time and a place to run them; the labs run each engine as a multi-node cluster, one container or VM per node.

## Alternatives considered

- **Trust managed-service defaults.** Reasonable for the failover itself; restores and data-level mistakes still need a rehearsed procedure.

## Evidence

<!-- evidence:start -->
- **8 of 8** failover scenarios passed. My own test plan, executed on Docker with 8 CPU / 12.5 GB. Source: [db-failover-lab/RESULTS.md](https://github.com/technobasant/db-failover-lab/blob/main/RESULTS.md)
- **10–20 s** observed promotion window after SIGKILL. SIGKILL of the Patroni leader, then patronictl polled every 10 s until the survivor showed as Leader — so 10 s is the measurement resolution, not the precision of the result. Source: [postgres-ha-lab/README.md](https://github.com/technobasant/postgres-ha-lab/blob/main/README.md)
- **~5 s** replica rebuilt from backup. Patronictl reinit; the pgBackRest restore itself logged 5,020 ms, then Patroni reported the replica created. Source: [postgres-ha-lab/README.md](https://github.com/technobasant/postgres-ha-lab/blob/main/README.md)
- **5 of 5** rows recovered by point-in-time restore. Dropped a table, restored to a timestamp taken before the DROP, counted rows against the pre-incident total. Source: [postgres-ha-lab/README.md](https://github.com/technobasant/postgres-ha-lab/blob/main/README.md)
- **909,968** rows recovered by snapshot rollback. An over-broad DELETE (a WHERE reaching years further back than intended), then ALTER TABLE EXECUTE rollback_to_snapshot, counted against the pre-incident total. Source: [lakehouse-lab/MEASUREMENTS.md](https://github.com/technobasant/lakehouse-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- db-failover-lab [RESULTS](https://github.com/technobasant/db-failover-lab/blob/main/RESULTS.md)
- postgres-ha-lab [README](https://github.com/technobasant/postgres-ha-lab#readme)
