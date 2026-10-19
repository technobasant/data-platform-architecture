# 0005. Databricks or Snowflake: decided by a two-week proof of concept on fixed criteria

- Status: Proposed
- Date: 2026-10-19
- Deciders: CTO, CFO, data lead; proposed by the architect
- Evidence:

## Context

Both vendors have pitched, and on paper both meet the stage-1 requirements
([4. Options](../docs/04-options.md)). At the client's scale the list-price bill does not
separate them. What does is how each handles this client's data and constraints, which
can be measured. The criteria and their weights are fixed here, before the proof of
concept runs, so the result cannot be argued backwards.

## Decision drivers

- The stage-1 requirements, Q1 to Q15.
- A team of two to four.
- The budget, measured on the client's workload rather than assumed.
- Stage 3: an assistant on governed tables.

## Options

| | Strengths for this client, on paper | Open questions the PoC answers |
|---|---|---|
| Databricks | Delta on the client's S3 with UniForm; Unity Catalog row filters, column masks and audit; Auto Loader and Lakeflow; AI/BI Genie | the PostgreSQL CDC connector is in Public Preview; the bill for a small, bursty SQL workload on serverless |
| Snowflake | least to operate for SQL-first work; Openflow PostgreSQL connector generally available; masking and row access policies; Cortex Analyst | Enterprise edition is needed for masking and row access policies and for Time Travel past one day; erasure through 7 days of Fail-safe |
| AWS-native (control) | the lowest bill; data stays open in the client's account | how much assembly a team of two can carry |

## Decision

Run the same work on Databricks and Snowflake for two weeks, with the AWS-native option
priced as the control, and score them:

| # | Criterion | Weight | How it is measured | Must pass |
|---|---|---:|---|---|
| 1 | Correct numbers | gate | the dbt project builds unchanged on both; revenue by plan reconciles to the Stripe export to the cent | yes |
| 2 | Ingestion | 20 | the [ten-day delivery test](https://github.com/technobasant/data-stack-lab/tree/main/databricks) and CDC from a Postgres replica: events missing, duplicated, and the effort to make both zero | zero missing, zero duplicated |
| 3 | Governance | 20 | a row filter per account and a mask on personal columns, attacked by the isolation tests; the audit query for Q13 | no cross-account row |
| 4 | Erasure | 15 | time from delete to unrecoverable, through time travel and any fail-safe; the proof query | inside 30 days |
| 5 | Cost | 20 | credits or DBUs for a week of the daily build and the BI query set, from the platform's billing tables, projected to 12 and 36 months | under budget at 36 months |
| 6 | Speed | 10 | the BI query set at concurrency 2 and 8 | |
| 7 | Operability | 15 | moving parts the team runs; Terraform coverage of users, roles, grants and policies; what broke and how long it took to fix | |

The higher weighted score wins. A tie within 5 points goes to the lower measured cost at
36 months.

## Consequences

- Two weeks of the data team's time, and two trial accounts.
- The recommendation becomes a measured result the CFO can check, instead of a preference.
- Whichever loses, the dbt project and the contracts stay portable, so the decision can be
  revisited at the cost of moving ingestion and policies, not the models.

## Revisit when

The proof of concept completes: this record becomes Accepted with the scores as evidence.
After that, at contract renewal, or if the measured bill passes the budget.

## Evidence

<!-- evidence:start -->
Not measured yet; see the status above.
<!-- evidence:end -->
