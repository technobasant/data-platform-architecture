# 0007. Freshness is an SLO measured from the consumer's side and alerted on burn rate

- Status: Accepted
- Date: 2026-10-18
- Evidence: stream_freshness_p99, stream_stall_page, registry_breach_delay

## Context

"The job is running" says nothing about whether the data is fresh. A stream can be up and stalled; a batch can succeed on yesterday's input.

## Decision

- Each served dataset has a freshness objective owned by its producing team (see [0004](0004-contracts-with-acknowledgement.md)).
- Freshness is measured where consumers read: probe events written at the source are timed until they are queryable at the serving layer.
- Alerts fire on multi-window burn rate, not on single breaches.
- Batch datasets record freshness from their last successful write, evaluated on an interval.

## Consequences

- At 1,000 events a second, p99 from event time to queryable in the serving store was 6.1 s.
- A frozen pipeline paged in 59–62 s.
- An interval evaluator notices a breach half an interval late at the median (7.5 s at a 15 s interval): the interval is part of the objective.

## Alternatives considered

- **Alert on job state.** Misses stalls and stale inputs.
- **Alert on every breach.** Pages on noise; burn rate pages on budget.

## Evidence

<!-- evidence:start -->
- **6.1 s** p99 from event time to queryable in ClickHouse at 1,000 events/s. ClickHouse ingest time minus event time for every on-time event, median of three 90 s runs; the floor is the 5 s checkpoint interval at which Flink's transactions commit. Source: [streaming-platform/MEASUREMENTS.md](https://github.com/technobasant/streaming-platform/blob/main/MEASUREMENTS.md)
- **59–62 s** from a frozen pipeline to a firing burn-rate alert. Both TaskManagers paused for 150 s at 500 events/s; freshness probes every 5 s; multi-window burn-rate rules compressed 12× from the 1 h/5 m pair; alert state polled every second. Source: [streaming-platform/MEASUREMENTS.md](https://github.com/technobasant/streaming-platform/blob/main/MEASUREMENTS.md)
- **7.5 s** median freshness-breach detection delay at the 15 s default. 200 datasets with a 60 s SLO whose deadlines fall evenly over two evaluator intervals; delay = detected_at − deadline as the registry recorded it. Source: [dataset-registry/MEASUREMENTS.md](https://github.com/technobasant/dataset-registry/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- streaming-platform [0007 A freshness SLO measured by probes, alerted on burn rate](https://github.com/technobasant/streaming-platform/blob/main/docs/adr/0007-freshness-slo-probes.md)
- dataset-registry [0005 Freshness from the last successful write](https://github.com/technobasant/dataset-registry/blob/main/docs/adr/0005-freshness-from-last-successful-write.md)
