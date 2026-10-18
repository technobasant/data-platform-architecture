# 0005. Keep history for every attribute that facts are read against

- Status: Accepted
- Date: 2026-10-18
- Evidence: dsl_type1_misattributed, dsl_type2_correct, dsl_snapshot_coverage

## Context

Reports attribute facts to attributes of a customer: revenue by plan, usage by region, churn by segment. Those attributes change. A dimension that overwrites them in place answers "what did customers who are on this plan now pay", not "what did this plan earn".

## Decision

- Attributes that facts are read against are modelled as Type 2 dimensions: one row per version, valid over `[valid_from, valid_to)`.
- Facts join to the version in effect when they happened, with a left join and a not-null test on the key.
- The first version reaches back to the entity's creation; open versions end at a far-future date, not NULL.
- History is built from the change source (CDC, [0001](0001-three-ways-in.md)) where intermediate states matter, and from snapshots of extracts otherwise.

## Consequences

- A Type 1 dimension put 15.1% of a year's revenue on the wrong plan, with totals that still reconciled. The Type 2 dimension put all 5,048 invoices on the plan they billed.
- Snapshots of monthly extracts saw 533 of 570 changes; facts dated between extracts inherit the gap.
- Dimensions grow with every change, and every fact join becomes a range join.

## Alternatives considered

- **Type 1 everywhere.** Correct only for attributes nothing is ever reported against historically.
- **Copy the attribute onto every fact at write time.** Correct for that attribute, and every new question needs a backfill.

## Evidence

<!-- evidence:start -->
- **15.1%** of a year's revenue on the wrong plan with a Type 1 account dimension. 5,048 synthetic invoices (seed 7, Oct 2025 – Sep 2026) attributed by each account's current plan and compared with the plan the generator billed; $152,227 of $1,010,202. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **5,048 of 5,048** invoices on the plan they billed, Type 2 dimension from dbt snapshots. As-of join of each invoice to the dim_account version in effect at billing, scored against the generator's truth file; the dimension was built from 13 monthly snapshot loads. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **533 of 570** account changes in a year seen by monthly snapshots. A change counts as seen if a snapshot version starts at its exact updated_at; signups excluded. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- data-stack-lab [dbt project decisions](https://github.com/technobasant/data-stack-lab#decisions)
