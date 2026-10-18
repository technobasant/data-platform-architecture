# 0003. Exactly-once by transactions upstream, idempotence at the edge, and counts reconciled per layer

- Status: Accepted
- Date: 2026-10-18
- Evidence: stream_failure_exactness, stream_window_undercount

## Context

Brokers and stream workers fail. A pipeline that is only at-least-once double-counts after every failure; one that is at-most-once loses data. Not every sink can take part in a transaction.

## Decision

- Kafka transactions and the stream processor's two-phase commit carry every record exactly once into the lakehouse.
- Sinks that cannot join a transaction (a real-time OLAP store) are made idempotent: they deduplicate by event id, so a replayed batch overwrites instead of adding.
- Every layer's count is reconciled against the source after every failure test.
- Windowed aggregates are checked separately, because exactly-once records do not imply exact window counts: late records after a failure fall outside windows that have already closed.

## Consequences

- In every one of nine failure runs (broker kills, worker kills, stalls), every record layer was exact.
- In the worst broker kill, the 10-second window counts held only 59.8% of on-time events. Aggregates that must be exact are recomputed from the record layer, not trusted from the stream.
- Transactions add latency: consumers read committed data only, at checkpoint intervals.

## Alternatives considered

- **At-least-once everywhere with downstream deduplication.** Simpler producers; every consumer must deduplicate, and most forget.
- **Allowed lateness with updating windows.** Turns window output into a changelog that append-only sinks cannot apply.

## Evidence

<!-- evidence:start -->
- **9 of 9** failure runs with every event layer exact. Three controller-broker kills, three TaskManager kills and three 150 s stalls under load; Kafka, ClickHouse, Iceberg and the dead-letter topic reconciled against the generator's ledger by sequence number. Source: [streaming-platform/MEASUREMENTS.md](https://github.com/technobasant/streaming-platform/blob/main/MEASUREMENTS.md)
- **59.8%** of on-time events left in the window counts after one broker kill. 118,229 of 197,749 on-time events counted in their 10 s windows in the worst of three broker-kill runs; the rest went to the late side output because catch-up reordered partitions past the 5 s watermark bound. Source: [streaming-platform/MEASUREMENTS.md](https://github.com/technobasant/streaming-platform/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- streaming-platform [0004 Exactly-once by transactions upstream, idempotence at the edge](https://github.com/technobasant/streaming-platform/blob/main/docs/adr/0004-exactly-once-end-to-end.md), [0006 Deduplication by arrival, windows by event time](https://github.com/technobasant/streaming-platform/blob/main/docs/adr/0006-event-time-dedup-and-late-data.md)
