# 0002. Iceberg tables on object storage, behind a catalog that vends scoped credentials

- Status: Accepted
- Date: 2026-10-18
- Evidence: lakehouse_rollback, lakehouse_compaction, lakehouse_partition_prune

## Context

Several engines need the same tables: a stream processor writes them, a SQL engine serves analysts, a serving store reads aggregates, and a managed warehouse may join later. If one engine owns the storage, every other engine needs a copy.

## Decision

The system of record is Apache Iceberg tables on object storage, registered in an Iceberg REST catalog. Engines never hold storage keys: the catalog vends credentials scoped to the table and the operation. Compaction and snapshot expiry run on a schedule, and snapshot retention is set longer than the time it takes to notice a bad write.

## Consequences

- Engines are replaceable. A second engine read the same tables through the same catalog with no copy.
- A bad write can be undone: a snapshot rollback restored 909,968 rows.
- Maintenance is the platform's job. Frequent writes leave many small files, and compaction is what merges them (20 files into 1 per partition in the lab); expiring snapshots too eagerly removes the rollback window, so retention is a recovery decision, not a storage one.
- The catalog becomes critical infrastructure: it needs the same availability and backup discipline as a database.

## Alternatives considered

- **Warehouse-native storage** (Snowflake, BigQuery). Less to operate; every other engine goes through the warehouse or a copy.
- **Delta Lake.** Equally valid, and the natural choice when Databricks is the main engine; interoperability with other engines goes through UniForm or Delta readers.
- **Plain Parquet with a Hive metastore.** No snapshot isolation, no rollback.

## Evidence

<!-- evidence:start -->
- **909,968** rows recovered by snapshot rollback. An over-broad DELETE (a WHERE reaching years further back than intended), then ALTER TABLE EXECUTE rollback_to_snapshot, counted against the pre-incident total. Source: [lakehouse-lab/MEASUREMENTS.md](https://github.com/technobasant/lakehouse-lab/blob/main/MEASUREMENTS.md)
- **20 → 1** files merged per partition by optimize. Twenty 5,000-row inserts into one partition, then ALTER TABLE EXECUTE optimize, counted from the $files metadata table. Source: [lakehouse-lab/MEASUREMENTS.md](https://github.com/technobasant/lakehouse-lab/blob/main/MEASUREMENTS.md)
- **88 ms** one-month predicate over 1.5M Iceberg rows. Median of 7 server-side runs from system.runtime.queries, after 2 warm-ups, on a month-partitioned Iceberg table. Source: [lakehouse-lab/MEASUREMENTS.md](https://github.com/technobasant/lakehouse-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- streaming-platform [0005 Iceberg through the REST catalog](https://github.com/technobasant/streaming-platform/blob/main/docs/adr/0005-iceberg-rest-catalog.md)
