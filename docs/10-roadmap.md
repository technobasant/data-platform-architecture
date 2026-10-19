# 10. Roadmap

About thirteen months, from the stopgap to the assistant, with the decisions each step
waits for. Costs are the platform's vendor bill from the [cost model](04-options.md#cost)
on list prices and stated assumptions; the proof of concept replaces them with measured
figures.

## Weeks 0–26: stage 0 to the platform live

| Weeks | Work | Decision or deliverable | Who |
|---|---|---|---|
| 0–2 | stage 0: every BI query moves to the replica, with the replica's settings in [0001](../decisions/0001-analytics-off-the-product-database.md); analysts get personal roles on the replica, replacing the shared login, before the SOC 2 audit window opens in month 3 | the primary serves no BI query | data team |
| 0–4 | the reader inventory: every reader of the replica and the BI tool's query log, over a month | the inventory [8. Migration](08-migration.md)'s waves are built from | data team |
| 2–6 | the proof of concept on both platforms: two weeks of setup (trials, data, access), then two weeks of measured runs, as [0005](../decisions/0005-databricks-or-snowflake.md) has it; procurement, the DPA and the security review start in parallel | scores on criteria fixed in advance | data team, the architect; procurement, legal |
| 6 | the platform decision | [0005](../decisions/0005-databricks-or-snowflake.md) accepted, with scores | CTO, CFO, data lead |
| 6–10 | contract and security review complete; Terraform foundations | the platform exists, empty, governed | the architect, the analytics engineer |
| 10–16 | wave 1: CDC from the product's primary, Stripe files, the star schema, the backfill of events older than 90 days from the S3 exports (reconciled by each file's row count), quality gates, reconciliation running daily against the replica | reconciliation green or explained for 10 consecutive days; Q4 holds for the period the exports cover | analytics engineer; the two data engineers, hired and started in week 12 (month 3) |
| 16–20 | wave 2: finance dashboards and board-pack exports on the platform | one month-end close produced from the platform, signed off by the CFO | data team, finance |
| 20–24 | wave 3: product and customer-success dashboards; ad hoc SQL moved to personal roles | the replica has served no BI query for 2 weeks | data team |
| 24–26 | wave 4: retire the replica's reporting role; the erasure drill; delete the S3 exports once the backfill has reconciled | erasure drill passes; exports gone | data team, security lead |

Only the replica's personal roles are in place before the SOC 2 audit window opens in
month 3; the platform's own access reviews, audit logs and change controls complete through
waves 1 and 2, by month 5.

## Months 6–13: stage 2 and the assistant

| Month | Milestone | Stage | Platform bill (list price, modelled) |
|---|---|---|---|
| 4 | finance on the platform (wave 2) | 1 | about $370–770 a month |
| 6 | stage 1 done (wave 4); stage 2 starts: the event stream agreed with product; [0010](../decisions/0010-customer-usage-serving.md) decided | 1 done → 2 | |
| 9 | the usage page reads the usage store; isolation tests on its path | 2 | stream and store added: priced at the decision |
| 10 | stage 2 done: Q11 and Q12 met | 2 done | about $730–1,540 a month for the platform |
| 10–13 | the assistant on governed marts ([AI architecture](https://github.com/technobasant/ai-platform-architecture)) | 3 | model costs in the AI architecture |

Stage 3 finishes around month 13, a month past the twelve months
[the brief](01-brief.md#why-now) asks for: stage 1's longer timeline (weeks 0–26, not the
sixteen weeks first assumed) pushes both later stages back by the same amount.

## Team

| Weeks | People | Focus |
|---|---|---|
| 0–12 | analytics engineer, analyst, the architect part time | stopgap, reader inventory, proof of concept, foundations, wave 1 starting |
| 12–26 | plus two data engineers (hired and started week 12, month 3) | waves 1–4: migration, governance, the erasure drill |
| 26+ | four | stage 2, the assistant's data, operations |

## What would change the plan

- The proof of concept shows a requirement neither platform meets: re-open the AWS-native
  option before buying.
- Growth runs well ahead of the growth plan (about threefold in the first year, then
  roughly 2.2 times a year): the cost projection is re-run monthly from measured usage, and
  the 36-month figures move up.
- The product team cannot take on the event stream in month 6: stage 2 slips, and the usage
  page keeps reading the primary, which [0001](../decisions/0001-analytics-off-the-product-database.md)
  accepts as the one remaining analytical load on it.
