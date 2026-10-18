# 0006. Incremental loads take the run's data interval and replace by key; schedules name their timetable

- Status: Accepted
- Date: 2026-10-18
- Evidence: dsl_backwards_loss, dsl_default_daily_loaded

## Context

Daily loads are re-run, backfilled and occasionally run out of order: a file lands late, a day is cleared, a backfill runs newest-first. An incremental load that decides "what is new" from its own high-water mark remembers how far it got, not what it has seen.

## Decision

- Each run loads exactly what arrived inside its data interval, and writes by replacing its partition or merging on a key, so a re-run of any day reloads that day and nothing else.
- DAGs name their timetable. On Airflow 3, cron strings default to a trigger timetable whose data interval is a single instant, so `CronDataIntervalTimetable` is set explicitly, and a test asserts that a run's window is one day long.
- A missing input fails the run without retries; the day is re-run when the input lands.

## Consequences

- Backfilled newest day first, two high-water-mark models lost 96.56% of a month with every run green. The interval-based model lost nothing in any order.
- On Airflow 3's default `@daily`, the same interval-based model loaded 0 of 89,508 events in 30 successful runs. The explicit timetable and the test are what stand between the two outcomes.
- Event-time watermarks are not used for completeness at all: in order, one lost 2,034 of 2,291 late events.

## Alternatives considered

- **High-water mark on arrival time.** Complete only while runs happen in order.
- **Full refresh daily.** Correct and simple until the data outgrows the window.

## Evidence

<!-- evidence:start -->
- **96.56%** of a month's events lost by high-water-mark loads backfilled newest day first, every run green. September 2026 backfilled through an Airflow 3.3 DAG, one run a day from the 30th back to the 1st; event-time and arrival-time watermark models scored against the 89,508 events that arrived. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **0 of 89,508** events loaded by a data-interval incremental model on Airflow 3's default @daily, in 30 successful runs. The same DAG on schedule "@daily", which Airflow 3.3 turns into a CronTriggerTimetable (create_cron_data_intervals = False); each run's data interval starts and ends at the instant it fires. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- data-stack-lab [Airflow project](https://github.com/technobasant/data-stack-lab/tree/main/airflow)
