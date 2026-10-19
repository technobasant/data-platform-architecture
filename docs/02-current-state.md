# 2. Current state

Every report, dashboard and export reads the product's Postgres. This section measures what
that costs, on a lab copy of the client's database at today's scale, and records the other
problems the brief describes.

## How it was measured

[`baseline/`](../baseline) builds the client's database in Docker: a Postgres 17 primary and
a streaming read replica, 2 vCPU and 4 GB each, with 6,000 accounts, 60,000 users and 90 days
of events (31.5 million rows, 5 GB with indexes). The product's own request (a customer's
usage page, an activity update and an event insert) runs at 100 a second, about half what
the lab primary can serve. Two analysts run the BI tool's four queries in turn: revenue by
plan and month (0.1 s on an idle primary), daily active users by plan over 90 days (49 s),
the weekly event mix (90 s) and the top accounts of the last 30 days (15 s). Each scenario
runs for five minutes, after a checkpoint and with the replica caught up.

Results: [`results/baseline.json`](../results/baseline.json), Postgres 17.11, one run on
2026-10-19.

## Reports on the primary slow the product down

| The product's requests | p50 | p95 | p99 | Over 100 ms |
|---|---:|---:|---:|---:|
| No reports running | 4.9 ms | 93 ms | 483 ms | 4.8% |
| Reports on the primary | 14.3 ms | **794 ms** | 1,847 ms | **23.0%** |

With two analysts' reports on the primary, the product's 95th-percentile request took 8.5
times as long, and almost a quarter of requests took over 100 ms. The reports read the
whole events table, pushing the product's recent pages out of memory and taking its CPUs.
This is the month-end slowdown in [the brief](01-brief.md#why-now), and why every report
belongs on the replica until the platform exists.

## Reports on the replica are cancelled

| Reports on the replica | Runs | Finished | Cancelled by recovery conflict |
|---|---:|---:|---:|
| The three long reports, default settings | 412 | **3** | 409 |
| The short revenue report, default settings | 138 | 73 | 65 |
| The three long reports, `hot_standby_feedback = on` | 20 | 20 | 0 |
| The short revenue report, `hot_standby_feedback = on` | 7 | 7 | 0 |

The product updates `users` constantly, and Postgres's cleanup of the old row versions is
replayed on the replica. A report still reading those versions blocks the replay; after
`max_standby_streaming_delay` (30 s) the replica cancels it. In the lab, once the replica had
fallen 30 s behind, it cancelled conflicting queries at once: the median cancelled report ran
for 0.1 s, and even the 0.1-second revenue report was cancelled 65 times. The analysts in the
lab retried immediately, as people do, and in five minutes three long reports finished.

With `hot_standby_feedback` on, the replica tells the primary which row versions its queries
still need, and every report finished. The price is paid on the primary: cleanup of the
product's busiest tables is held back for as long as the longest report runs. With reports
of one to two minutes that was not visible in a five-minute window (the `users` table's dead
rows went from 8,593 to 3,551 as autovacuum ran); a report that runs for an hour holds back an
hour of the product's cleanup, every time it runs. The trade is between reports that fail and
a product database that bloats, and neither is acceptable as the design.

## What else the brief describes

| Problem | Evidence |
|---|---|
| Revenue by plan disagrees with billing | every invoice is reported under the account's current plan; on the same shape of data that puts 15.1% of a year's revenue on the wrong plan ([measured](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)) |
| History stops at 90 days | the events table is cut back nightly; older events go to S3 as CSV and are not read |
| No access trail | one database login for the BI tool and the analysts' SQL |
| No erasure path | personal data in the replica, the CSV exports and the BI tool's caches, with no process to find it |
| Freshness is nobody's | the cron jobs either run or do not; nothing checks that yesterday is complete |

## Limits of the measurement

The lab is Docker on a laptop, not RDS. The primary and the replica share one host's disk,
so in the two replica scenarios the product's latency also rose (p95 561 ms and 509 ms);
on RDS they are separate machines and that effect would not appear, so it is not used as
evidence. Absolute latencies, especially at the 99th percentile, include the virtual disk's
flush times. The comparison on the primary, and the counts of finished and cancelled
reports, are the results.
