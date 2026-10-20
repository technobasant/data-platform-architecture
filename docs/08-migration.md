# 8. Migration

From the current state to stage 1 with one planned restart of the primary, one consumer at
a time, with a way back at every step. `rds.logical_replication` is a static parameter, so
turning it on takes one restart, in a maintenance window agreed with the product team; after
that, the product's database is not changed again, and the only new ongoing thing it sees
is a logical replication slot.

## Inventory

Everything that reads the product's database today, and what happens to it.

| Reader | Today | Disposition | Moves in |
|---|---|---|---|
| Usage page (the product) | queries the primary | **retain** until stage 2 gives it a store of its own | stage 2 |
| Finance dashboards (revenue, MRR) | BI tool on the replica | **rebuild** on the marts; numbers change, by design | wave 2 |
| Board-pack exports | cron SQL on the replica, CSV to S3 | **rebuild** as platform jobs writing the same files | wave 2 |
| Product dashboards (usage, funnels) | BI tool on the replica | **migrate** to the marts | wave 3 |
| Customer-success health report | BI tool on the replica, 90 days only | **rebuild**, on full history | wave 3 |
| Ad hoc SQL by analysts | the replica, one shared login | **migrate** to the platform, personal roles | wave 3 |
| Exports of deleted events in S3 | written nightly, never read | **backfill** into `raw` in wave 1, reconciled by row count, then **retire**: deleted once the backfill has reconciled | wave 1 |

The inventory is built from the replica's `pg_stat_statements` and the BI tool's query log
over a month, not from memory: queries nobody remembers are the ones that break.

## Waves

Between wave 0 and wave 1, weeks 2–10, the proof of concept decides the platform
([0005](../decisions/0005-databricks-or-snowflake.md)), and the contract, the security
review and the Terraform foundations complete; the full week-by-week timeline, and who does
each part, is in [10. Roadmap](10-roadmap.md).

| Wave | Weeks | Work | Exit criteria |
|---|---|---|---|
| 0 | 0–2 | every BI query on the replica; analysts get personal roles on the replica, replacing the shared login | the primary serves no BI query |
| 1 | 10–16 | platform in Terraform; CDC into `raw`; Stripe files; the star schema; the backfill of events older than 90 days from the S3 exports, reconciled by each file's row count; tests; reconciliation running daily against the replica | reconciliation green or explained for 10 consecutive days; Q4 holds for the period the exports cover |
| 2 | 16–20 | finance dashboards and board-pack exports on the platform | the CFO signs off one month-end close produced from the platform |
| 3 | 20–24 | product and customer-success dashboards; ad hoc SQL moved to personal roles | the replica has served no BI query for 2 weeks |
| 4 | 24–26 | retire the replica's reporting role; the erasure drill; delete the S3 exports once the backfill has reconciled | erasure drill passes; exports gone |

## Running both

From wave 1 to the end of wave 3 the old and new paths run side by side, and a
reconciliation job compares them every morning:

| Check | Old side | New side | Pass |
|---|---|---|---|
| Rows per table | the replica | `staging` | equal, after CDC lag |
| Events per day, last 90 days | the replica | `fct_events` | equal |
| Invoice totals per month | Stripe export | `fct_invoices` | equal to the cent |
| Revenue by plan per month | the old dashboard's query | `revenue_by_plan` | **not** equal: the old one is wrong. Every difference is attributed to invoices whose account changed plan, and the total of the differences is zero |

The last row is the one people need to see. The new revenue by plan disagrees with the old
on purpose, by about 15% of a year's revenue on this business's shape of data, and the
reconciliation shows exactly which invoices move and why. That is what makes finance trust
a number that changed.

## Cutover and rollback

- **One consumer at a time.** A dashboard moves when its numbers have matched, or differed
  only as explained, for 10 working days and its owner signs off.
- **The way back** is to point the dashboard at the replica again. The replica keeps its
  reporting role until 4 weeks after the last dashboard has moved.
- **The usage page** does not move in stage 1, so no customer-facing path depends on the
  migration.
- **CDC** can be stopped at any point by dropping the slot; the product is unaffected.

## What is measured, and what is not yet

The waves, the reconciliation and the rollback are designed here. The proof of concept
builds the reconciliation suite on both platforms against the lab copy of the company's
database ([2. Current state](02-current-state.md)); until then, the times in the waves
are estimates for a team of two growing to four.

---

[← 7. Security and governance](07-security-and-governance.md) · [README](../README.md) · [9. Operations →](09-operations.md)
