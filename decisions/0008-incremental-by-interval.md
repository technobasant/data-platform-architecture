# 0008. Incremental models load their run's window and replace it by key

- Status: Accepted
- Date: 2026-10-19
- Deciders: data lead; proposed by the architect
- Evidence: dsl_backwards_loss, dsl_default_daily_loaded, dsl_spark_static_overwrite

## Context

Rebuilding every model from all history each night is affordable today and not at 760
million events. Incremental models are the answer, and the common way to write them (load
what is newer than the newest row already loaded) breaks as soon as a day is re-run, a
backfill runs in any order but oldest first, or a file arrives late.

## Decision drivers

- Q6: re-runs, out-of-order backfills and late files lose nothing and double nothing.
- Q5: yesterday complete by 06:00 UTC.
- Cost: incremental, not full rebuilds, past 12 months.

## Options

| | Re-run of a day | Backfill newest first | Late file | Cost |
|---|---|---|---|---|
| Full rebuild nightly | ✔ | ✔ | ✔ | ✘ grows with history |
| High-water mark on event time | ✘ | ✘ 96.56% of a month lost | ✘ | ✔ |
| High-water mark on arrival time | ◐ | ✘ | ◐ | ✔ |
| **The run's window, replaced by key** (`delete+insert` or `MERGE` on the window, or `REPLACE WHERE`) | ✔ | ✔ | ✔ with a look-back | ✔ |

## Decision

Each incremental model takes the run's window as a parameter (the data interval the
scheduler passes) plus a fixed look-back for late arrivals, and replaces that window by key.
Schedules are written with an explicit timetable that has an interval; a default schedule
whose window is empty is a test failure. Re-writing part of a table uses the platform's
predicate-scoped replace (`REPLACE WHERE`, or a `MERGE` on the window), never an
overwrite that can replace the whole table.

## Consequences

- Every day can be re-run on its own, in any order, as an ordinary operation
  ([9. Operations](../docs/09-operations.md)).
- The look-back is a cost knob: wider catches later files and re-reads more.
- A run that loads nothing for a window that should have data fails, instead of passing
  green with zero rows.

## Revisit when

A model's window becomes too large to replace within the batch window, which on these
volumes is past the 36-month plan.

## Evidence

<!-- evidence:start -->
- **96.56%** of a month's events lost by high-water-mark loads backfilled newest day first, every run green. September 2026 backfilled through an Airflow 3.3 DAG, one run a day from the 30th back to the 1st; event-time and arrival-time watermark models scored against the 89,508 events that arrived. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **0 of 89,508** events loaded by a data-interval incremental model on Airflow 3's default @daily, in 30 successful runs. The same DAG on schedule "@daily", which Airflow 3.3 turns into a CronTriggerTimetable (create_cron_data_intervals = False); each run's data interval starts and ends at the instant it fires. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **1 of 365** daily partitions left after re-running one day with Spark's default static overwrite. PySpark 4.2.0, a 365-day rollup written with partitionBy(activity_date); one day recomputed and written back with mode("overwrite"); dynamic partitionOverwriteMode kept all 365. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
