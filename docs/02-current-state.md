# 2. Current state

Every report, dashboard and export reads the product's Postgres. This section measures what
that costs, on a lab copy of the client's database at today's scale, and records the other
problems the brief describes.

## How it was measured

[`baseline/`](../baseline) builds the client's database in Docker: a Postgres 17 primary and
a streaming read replica, 2 vCPU and 4 GB each, with 6,000 accounts, 60,000 users and 90 days
of events (31.5 million rows, 5 GB with indexes). The product's own request (a customer's
usage page, an activity update and an event insert) runs at a fixed rate. Each request
records one event, so the rate is the brief's event rate: 12 a second, about three times the
daily average of 4 (350,000 a day), a weekday peak. Two analysts run the BI tool's four
queries in turn; on the primary under that load their medians were 0.4 s (revenue by plan
and month), 62 s (daily active users by plan over 90 days), 90 s (the weekly event mix) and
24 s (the top accounts of the last 30 days). Each scenario runs for five minutes, after a
checkpoint and with the replica caught up.

Results: [`results/baseline-brief-rate.json`](../results/baseline-brief-rate.json), Postgres
17.11, one run on 2026-10-19. An earlier run at 100 requests a second, a stress rate about 25
times the brief's average, is in [`results/baseline.json`](../results/baseline.json); it
showed the same effects, larger.

## Reports on the primary slow the product down

| The product's requests, at 12 a second | p50 | p95 | p99 | Over 100 ms |
|---|---:|---:|---:|---:|
| No reports running | 9.2 ms | 40 ms | 208 ms | 2.2% |
| Reports on the primary | 34.2 ms | **525 ms** | 1,208 ms | **24.0%** |

With two analysts' reports on the primary, the product's 95th-percentile request took 13
times as long, and a quarter of requests took over 100 ms (at the stress rate: 93 to 794 ms,
4.8% to 23.0%). The reports read the whole events table, pushing the product's recent pages
out of memory and taking its CPUs. This is the month-end slowdown in
[the brief](01-brief.md#why-now), and why every report belongs on the replica until the
platform exists.

## Reports on the replica are cancelled

| Reports on the replica, at 12 a second | Runs | Finished | Cancelled by recovery conflict |
|---|---:|---:|---:|
| The three long reports, default settings | 35 | **3** | 32 |
| The short revenue report, default settings | 12 | 8 | 4 |
| Every report, `hot_standby_feedback = on` | 11 | 11 | 0 |
| Every report, a replica for reports alone with `max_standby_streaming_delay` at 15 minutes | 7 | 7 | 0 |

The product updates `users` constantly, and Postgres's cleanup of the old row versions is
replayed on the replica. A report still reading those versions blocks the replay; after
`max_standby_streaming_delay` (30 s by default) the replica cancels it. Once the replica had
fallen 30 s behind, it cancelled conflicting queries at once, and the analysts in the lab
retried immediately, as people do: in five minutes, 3 of 35 long reports finished. At the
stress rate it was 3 of 412.

There are two ways to let the reports finish, and they put the cost in different places:

- **`hot_standby_feedback = on`.** The replica tells the primary which row versions its
  queries still need, and every report finished. The price is paid on the primary: cleanup
  of the product's busiest tables is held back for as long as the longest report runs. In
  five minutes the `users` table's dead rows rose from 3,111 to 3,630; a report that runs for
  an hour holds back an hour of the product's cleanup, every time it runs.
- **A replica for reports alone, with a long delay.** With `max_standby_streaming_delay` at
  15 minutes and feedback off, replay waits for a report instead of cancelling it. Every
  report finished, and the primary's cleanup was not held back (dead rows fell from 3,630 to
  3,206 as autovacuum ran). The price is paid on the replica: it fell behind by up to 4.7
  minutes (2.4 at the median). The product reads only the primary, and the reports need
  yesterday's data, so that lag costs nothing anyone uses; a report running longer than 15
  minutes would still be cancelled.

The second is the stopgap until the platform exists ([0001](../decisions/0001-analytics-off-the-product-database.md)):
the replica becomes the reports' alone, and the product keeps the primary to itself.

## What else the brief describes

| Problem | Evidence |
|---|---|
| Revenue by plan disagrees with billing | every invoice is reported under the account's current plan; on the same shape of data that puts 15.1% of a year's revenue on the wrong plan ([measured](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)) |
| History stops at 90 days | the events table is cut back nightly; older events go to S3 as CSV and are not read |
| No access trail | one database login for the BI tool and the analysts' SQL |
| No erasure path | personal data in the replica, the CSV exports and the BI tool's caches, with no process to find it |
| Freshness is nobody's | the cron jobs either run or do not; nothing checks that yesterday is complete |

## Limits of the measurement

The lab is Docker on one host, not RDS. The primary and the replica share the host's disk,
so in the replica scenarios the product's latency also rose (p95 715 ms with default
settings, 421 ms with feedback, 701 ms with the long delay), and the reports themselves ran
slower on the delayed replica (the daily-active-users report took 219 s at the median, as
replay caught up on the same disk). On RDS the primary and replica are separate machines and
neither effect would appear, so neither is used as evidence. Absolute latencies, especially
at the 99th percentile, include the virtual disk's flush times. The comparison on the
primary, and the counts of finished and cancelled reports, are the results. The rate is the
brief's peak hour, held for five minutes; the nightly purge of events older than 90 days,
which adds its own cleanup, was not part of the run.

---

[← 1. Brief](01-brief.md) · [README](../README.md) · [3. Requirements →](03-requirements.md)
