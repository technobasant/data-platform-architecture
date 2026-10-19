# 0014. Quality gates: tests on rows, checks on the day, reconciliation to billing

- Status: Accepted
- Date: 2026-10-19
- Deciders: CFO, data lead; proposed by the architect
- Evidence: dsl_quality_block, dsl_mutants, dsl_type2_correct, dsl_volume_band_published

## Context

The CFO will judge the platform by whether revenue matches Stripe, and analysts by whether
a day is ever missing. Most data tests check rows that arrived; the incidents that hurt
most are rows that never arrived, and logic that is wrong but produces well-formed rows.

## Decision drivers

- Q3: revenue reconciled to Stripe to the cent.
- Q5, Q6: no missing or doubled day reaches a dashboard.
- Tests that are seen to fail, so a green build means something.

## Options

| | Wrong values | Missing rows | Wrong logic | Cost |
|---|---|---|---|---|
| Row tests only (not null, unique, relationships) | ✔ | ✘ | ✘ | ✔ |
| Plus anomaly detection on volumes | ✔ | ◐ inside a band | ✘ | ◐ |
| **Row tests, day-level checks against the producer's manifest and recent volume per group, unit tests on the logic, and reconciliation to billing; each proven by a deliberate break** | ✔ | ◐ a shortfall inside the accepted volume band is not held | ✔ | ◐ |

## Decision

Four layers, all in the build: row tests on what arrived; day-level checks (each file
against its manifest, volume against recent accepted days, each platform's share) that hold
the day; dbt unit tests on as-of joins and other logic; and a reconciliation of revenue to
the Stripe export. Failing rows are quarantined only where the check is row-level; a
day-level failure holds the day, unless the shortfall sits inside the accepted volume band,
in which case the day is promoted rather than held. A completeness check compares each
day's count against the source's own count: for CDC tables, reconciliation against the
replica; for files, the producer's manifest row count. CI breaks the models on purpose and
requires the tests to fail.

## Consequences

- A shortfall inside the accepted volume band is published, not held: in the sibling lab,
  27 September was promoted with 1,040 events withheld, because the shortfall sat inside the
  accepted 30% band. The volume check catches a day that falls outside what recent days
  would predict; it does not catch every missing row, which is why it is paired with the
  completeness check against the source's own count.
- Some good rows are held with a bad day outside the band, and a person releases them; that
  is the price of the check being conservative rather than silent.
- New checks need a deliberate break to prove them, which is a habit, not a tool.

## Revisit when

Held days happen more than twice a month, which means a check is too tight or a producer
needs a contract conversation.

## Evidence

<!-- evidence:start -->
- **0 of 3,198** bad rows promoted when any failing data-quality check held the day. September delivered daily with nine injected defects and checked in dbt (contract, row tests, batch tests against seven accepted days, manifest control totals); every delivered row labelled good or bad by its defect. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **4 of 4** deliberate model breaks that failed the build. Each break applied to a copy of the dbt project and built twice, with unit tests and with data tests only; recorded per engine and checked in CI. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **5,048 of 5,048** invoices on the plan they billed, Type 2 dimension from dbt snapshots. As-of join of each invoice to the dim_account version in effect at billing, scored against the generator's truth file; the dimension was built from 13 monthly snapshot loads. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **1,040** events withheld when 27 September was promoted, the shortfall inside the accepted 30% volume band. The day-level check compared 27 September's event count with recent accepted days; the shortfall sat inside the accepted 30% band, so the block policy promoted the day instead of holding it. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
