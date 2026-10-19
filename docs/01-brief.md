# 1. The brief

The client is fictional. Its data is the synthetic SaaS business that
[data-stack-lab](https://github.com/technobasant/data-stack-lab) generates, and its current
state is measured on a lab copy of its database ([2. Current state](02-current-state.md)).
Nothing here describes a real company.

## The client

A B2B SaaS company selling a collaborative reporting product to other businesses.

| | Today |
|---|---|
| Customer accounts | 6,000 on four plans: free, team ($49 a month), business ($199), enterprise ($899) |
| Users | about 60,000 |
| Product events | about 350,000 a day, growing roughly threefold a year as larger accounts sign |
| Revenue | about $18M a year; 40% from customers in the EU |
| Staff | about 140; product engineering 45 |
| Data team | one analytics engineer and one analyst; two data engineers approved to hire |

The product is a monolith on AWS in one EU region. Its database is Postgres on Amazon RDS:
one primary and one read replica. Everything the business knows about itself is read from
that database:

- the product's own **usage page**, where a customer sees their activity, queries the
  primary;
- the **BI tool** (Metabase) runs finance, product and customer-success dashboards on the
  replica;
- **nightly cron jobs** run SQL on the replica and write CSV files to S3 for finance;
- product events older than **90 days are deleted** from Postgres, because the table had
  grown too large; the deleted rows are exported to S3 first and nobody reads them;
- **billing** is in Stripe; the plan an account is on lives only in `accounts.plan_id`,
  overwritten when it changes.

## Why now

The CTO and the CFO commissioned this together after one quarter in which:

1. **The product slowed down at month end,** when finance and customer success ran their
   reports while the replica was being rebuilt and dashboards pointed at the primary.
2. **Revenue by plan in the board pack did not match billing.** Every past invoice was
   reported under the plan its account is on today. On the same shape of data, that puts
   15.1% of a year's revenue on the wrong plan
   ([measured](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)).
3. **Dashboards fail at random.** Long reports on the replica are cancelled with "conflict
   with recovery", and the analysts re-run them, sometimes several times.
4. **Two enterprise prospects asked for SOC 2 Type II and a data processing agreement**
   that commits to erasing a person's data within 30 days, everywhere it is held.
   Enterprise customers also want their usage in the product to be under a minute old,
   and an export of it.
5. **Product wants an assistant** that answers customers' questions about their own usage,
   within twelve months. That is the subject of the companion
   [AI architecture](https://github.com/technobasant/ai-platform-architecture).

## What was asked for

| Deliverable | Where it is |
|---|---|
| An assessment of the current state, with the problems measured | [2. Current state](02-current-state.md) |
| Requirements, with quality targets stated as testable scenarios | [3. Requirements](03-requirements.md) |
| The options, and a recommendation between Databricks and Snowflake, both of which have pitched | [4. Options](04-options.md), [decisions](../decisions) |
| A target architecture that can be reached in stages | [5. Target architecture](05-target-architecture.md) |
| The data model and the contracts at each source | [6. Data model](06-data-model.md) |
| Security, access, personal data and erasure, and the SOC 2 controls they support | [7. Security and governance](07-security-and-governance.md) |
| A migration off the current setup without disrupting the product | [8. Migration](08-migration.md) |
| How it is run, by a team of four | [9. Operations](09-operations.md) |
| A twelve-month roadmap with costs | [10. Roadmap](10-roadmap.md), [cost](../cost) |
| The decisions, and the risks | [decisions](../decisions), [risks](risks.md) |

## Stakeholders

| Who | Cares most about | Will judge the result by |
|---|---|---|
| CTO (sponsor) | the product's reliability; the team's ability to run what is built | no product incident caused by analytics; nothing the team cannot operate |
| CFO (sponsor) | numbers that agree with billing; cost | revenue by plan reconciled to Stripe to the cent; a bill inside the budget |
| VP Product | usage in the product; the assistant | customer usage under a minute old; a governed place for the assistant to read from |
| Head of Customer Success | account health across all history | reports on more than 90 days of activity |
| Security and compliance lead | SOC 2 Type II in nine months; the DPA | access reviews, audit logs, erasure that can be proven |
| Data team | not being on call for something fragile | one platform, managed, with tests that fail before a dashboard does |

## Constraints

- **People.** Two data people now, four by month six. The product's on-call rota does not
  include them, and the platform must not need a dedicated operator.
- **Money.** Platform run cost, including the vendor bill and anything self-hosted, under
  $15,000 a month in year one.
- **The product is not touched.** The application database stays Postgres on RDS. No
  migration step may need product downtime or a schema change the product team has not
  agreed to.
- **Compliance.** SOC 2 Type II audit window opens in month three. Erasure within 30 days of
  a request, including backups and copies, under the DPA.
- **One region.** Everything stays in the EU region the product runs in.
- **Managed first.** No self-run distributed system in year one unless a requirement cannot
  be met without it.

## Scale

The figures every sizing and cost statement uses. "Today" is measured; the rest are the
client's growth plan, and are assumptions.

| | Today | In 12 months | In 36 months |
|---|---:|---:|---:|
| Customer accounts | 6,000 | 12,000 | 40,000 |
| Product events per day | 350,000 | 1 million | 5 million |
| Event history kept | 90 days | 25 months | 25 months |
| Events held, at that day's rate over the history kept | 31.5 million | 760 million | 3.8 billion |
| Invoices per month | about 3,300 | 6,600 | 22,000 |

## Out of scope

The product's application architecture and its database's availability; machine learning
beyond the assistant; a second region; replacing the BI tool.
