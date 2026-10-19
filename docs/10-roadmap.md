# 10. Roadmap

Twelve months, from the stopgap to the assistant, with the decisions each step waits for.
Costs are the platform's vendor bill from the [cost model](04-options.md#cost) on list
prices and stated assumptions; the proof of concept replaces them with measured figures.

## The first 90 days

| Days | Work | Decision or deliverable | Who |
|---|---|---|---|
| 0–14 | BI queries moved to the replica only (stage 0); inventory of every reader from query logs | the primary serves no BI query | data team |
| 0–14 | proof of concept on Databricks and Snowflake, AWS-native priced as the control | [0005](../decisions/0005-databricks-or-snowflake.md) accepted, with scores | data team, the architect |
| 15–30 | contract with the chosen vendor; Terraform for both environments; identity by SCIM | the platform exists, empty, governed | data team |
| 15–45 | CDC from RDS into `raw`; Stripe files with manifests; contracts in the producers' CI | wave 1 begins ([8. Migration](08-migration.md)) | data team, product engineering, finance systems |
| 30–60 | the star schema, quality gates, reconciliation running daily against the replica | reconciliation green or explained for 10 days | data team |
| 60–90 | finance dashboards and board-pack exports on the platform | one month-end close from the platform, signed off by the CFO | data team, finance |

## The year

| Month | Milestone | Stage | Platform bill (list price, modelled) |
|---|---|---|---|
| 1 | proof of concept done; platform chosen | 0 → 1 | trial credits |
| 3 | finance on the platform; SOC 2 window opens with access, audit and change controls in place | 1 | about $370–770 a month |
| 4 | every dashboard on the platform; the replica's reporting role retired; erasure drill passed | 1 done | |
| 5 | stage 2 starts: the event stream agreed with product; [0010](../decisions/0010-customer-usage-serving.md) decided | 2 | |
| 8 | the usage page reads the usage store; isolation tests on its path | 2 | stream and store added: priced at the decision |
| 9 | stage 2 done: Q11 and Q12 met | 2 done | about $730–1,540 a month for the platform |
| 9–12 | the assistant on governed marts ([AI architecture](https://github.com/technobasant/ai-platform-architecture)) | 3 | model costs in the AI architecture |

## Team

| Month | People | Focus |
|---|---|---|
| 0–3 | analytics engineer, analyst, the architect part time | proof of concept, foundations, finance |
| 3–6 | plus two data engineers | migration waves 2–4, governance, stage 2 design |
| 6–12 | four | stage 2, the assistant's data, operations |

## What would change the plan

- The proof of concept shows a requirement neither platform meets: re-open the AWS-native
  option before buying.
- Growth runs well ahead of the threefold plan: the cost projection is re-run monthly from
  measured usage, and the 36-month figures move up.
- The product team cannot take on the event stream in month 5: stage 2 slips, and the usage
  page keeps reading the primary, which [0001](../decisions/0001-analytics-off-the-product-database.md)
  accepts as the one remaining analytical load on it.
