# 0001. Three ways in: events through Kafka, database changes through CDC, vendor exports as files

- Status: Accepted. The events path is built and measured; the CDC path is not yet built in the labs.
- Date: 2026-10-18
- Evidence: stream_failure_exactness, dsl_snapshot_coverage

## Context

The platform receives three kinds of data with different failure models. Product events are high-volume, append-only, delivered at least once, and sometimes late. Application database state (accounts, plans, users) is mutable, and its history matters for anything read against it. Vendor exports (billing, CRM) arrive as files on the vendor's schedule, with a schema the vendor owns.

## Decision

- **Events** go to Kafka with Avro schemas registered at FULL_TRANSITIVE compatibility, then exactly-once into the lakehouse (see [0003](0003-exactly-once.md)).
- **Database changes** are read from the database's log (change data capture) wherever history matters, so every intermediate state is kept. Full extracts remain acceptable for tables nothing is read against historically.
- **Vendor exports** land as files partitioned by the day they arrived, and are loaded by the orchestrator per data interval (see [0006](0006-incremental-by-interval.md)).

## Consequences

- Each path has one failure model and one recovery procedure.
- A periodic extract cannot see a change that was made and undone between two extracts. Monthly extracts missed 37 of 570 account changes in a year; CDC sees them all.
- CDC adds replication slots to operate. A slot that is lost on database failover is the common way CDC pipelines lose data, so slot failover has to be part of [0009](0009-rehearsed-recovery.md).
- Kafka is a cluster to run, or a managed service to pay for.

## Alternatives considered

- **Extracts for everything.** Simplest, and wrong wherever history matters (measured above).
- **Stream everything.** Vendor exports are not streams; wrapping files in a stream adds a moving part without adding information.

## Evidence

<!-- evidence:start -->
- **9 of 9** failure runs with every event layer exact. Three controller-broker kills, three TaskManager kills and three 150 s stalls under load; Kafka, ClickHouse, Iceberg and the dead-letter topic reconciled against the generator's ledger by sequence number. Source: [streaming-platform/MEASUREMENTS.md](https://github.com/technobasant/streaming-platform/blob/main/MEASUREMENTS.md)
- **533 of 570** account changes in a year seen by monthly snapshots. A change counts as seen if a snapshot version starts at its exact updated_at; signups excluded. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- streaming-platform [0001 Apache Kafka in KRaft mode](https://github.com/technobasant/streaming-platform/blob/main/docs/adr/0001-apache-kafka-kraft.md), [0003 Avro with FULL_TRANSITIVE compatibility](https://github.com/technobasant/streaming-platform/blob/main/docs/adr/0003-avro-full-transitive.md)
