# 0007. A Kimball star, with Type 2 history for every attribute a fact is reported by

- Status: Accepted
- Date: 2026-10-19
- Deciders: CFO, data lead; proposed by the architect
- Evidence: dsl_type1_misattributed, dsl_type2_correct, dsl_mutants

## Context

Finance reports revenue by plan, product reports usage by plan and segment, and both are
wrong today because the plan is read from the account's current row. The data team is two
people who write SQL; the BI tool and, in stage 3, the assistant read the result.

## Decision drivers

- Q3: every invoice on the plan it billed.
- Readable by analysts, the BI tool and the assistant without a modeller at hand.
- Portable between Databricks and Snowflake ([0005](0005-databricks-or-snowflake.md)).

## Options

| | Q3 correct attribution | Readable by analysts and the assistant | Effort for a team of two |
|---|---|---|---|
| Report straight off the replicated tables | ✘ current state only | ◐ | ✔ |
| One wide table per report | ◐ if built with history | ✔ | ✘ grows with every report |
| Data Vault, then marts | ✔ | ✘ needs the marts anyway | ✘ |
| **Kimball star: Type 2 dimensions for every attribute a fact is reported by, facts at a declared grain** | ✔ | ✔ | ✔ |

## Decision

Model the marts as a Kimball star in dbt. Every attribute a fact is read against (plan,
status, segment, country) is Type 2, built from the CDC change rows
([0002](0002-cdc-from-the-product-database.md)); each fact joins the version in effect
when it happened. Attributes nothing is read against stay Type 1. Revenue is reconciled to
Stripe in the build ([0014](0014-quality-gates.md)). The model is in
[6. Data model](../docs/06-data-model.md).

## Consequences

- Each fact needs an as-of join, which is easy to get wrong silently: the join is pinned
  by unit tests, and a deliberate break in CI checks that the tests catch it.
- History is only as good as the change capture behind it: monthly snapshots missed 37 of
  570 changes in a year; CDC sees them all.
- Data Vault's audit trail is not needed: the raw CDC rows keep every change.

## Revisit when

The number of source systems passes about ten, or several teams model independently;
both are reasons to look again at a raw vault beneath the marts.

## Evidence

<!-- evidence:start -->
- **15.1%** of a year's revenue on the wrong plan with a Type 1 account dimension. 5,048 generated invoices (seed 7, Oct 2025 – Sep 2026) attributed by each account's current plan and compared with the plan the generator billed; $152,227 of $1,010,202. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **5,048 of 5,048** invoices on the plan they billed, Type 2 dimension from dbt snapshots. As-of join of each invoice to the dim_account version in effect at billing, scored against the generator's truth file; the dimension was built from 13 monthly snapshot loads. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **4 of 4** deliberate model breaks that failed the build. Each break applied to a copy of the dbt project and built twice, with unit tests and with data tests only; recorded per engine and checked in CI. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
