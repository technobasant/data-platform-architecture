# 0009. Pipelines are scheduled by the platform's own jobs, not a separate orchestrator

- Status: Accepted
- Date: 2026-10-19
- Deciders: data lead; proposed by the architect
- Evidence: dsl_default_daily_loaded

## Context

Stage 1 has one source database, two file feeds and one dbt project, all on one platform.
A general-purpose orchestrator such as Airflow is one more system to run, upgrade and
understand, and its defaults decide what each run loads.

## Decision drivers

- A team of two to four, no operator.
- Q5, Q6: runs in order, re-runs and backfills with a defined window.
- Q15: failures handled in business hours.

## Options

| | Systems to run | Windows passed to models | Cross-system dependencies |
|---|---|---|---|
| Airflow, managed (MWAA) | ✘ one more, with its own upgrades | ✔ data intervals, if the timetable says so | ✔ |
| Dagster or Prefect, managed | ✘ one more | ✔ | ✔ |
| **The platform's jobs (Lakeflow Jobs, or Snowflake tasks) running dbt** | ✔ none | ◐ passed as job parameters | ◐ within the platform |

## Decision

dbt runs as a job of the chosen platform, with the run's window passed as a parameter, and
the ingestion services ([0002](0002-cdc-from-the-product-database.md),
[0003](0003-files-immutable-loads-by-key.md)) are the platform's own. Backfills are a job
run with a range of windows. No separate orchestrator in stage 1.

## Consequences

- One less system, and one less set of defaults: Airflow 3's `@daily`, for example, gives
  a run an empty window, which loaded nothing in 30 green runs in the Airflow lab.
- Dependencies outside the platform (a reverse-ETL push, an export to a customer) are
  limited to what the platform's jobs can trigger.
- Moving to an orchestrator later is a change to scheduling, not to models, because models
  take the window as a parameter ([0008](0008-incremental-by-interval.md)).

## Revisit when

Pipelines span three or more systems that the platform cannot schedule, or stage 2 adds a
streaming path whose operations need a single view with the batch jobs.

## Evidence

<!-- evidence:start -->
- **0 of 89,508** events loaded by a data-interval incremental model on Airflow 3's default @daily, in 30 successful runs. The same DAG on schedule "@daily", which Airflow 3.3 turns into a CronTriggerTimetable (create_cron_data_intervals = False); each run's data interval starts and ends at the instant it fires. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
