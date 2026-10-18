# 0010. Three layers of tests: logic on written rows, data on real rows, and breaks to prove both

- Status: Accepted
- Date: 2026-10-18
- Evidence: dsl_mutants, dsl_type2_correct

## Context

Data tests (unique keys, not-null columns, reconciliations) check shape. A join to the wrong version of a dimension produces valid keys and correct totals, so shape checks pass while the numbers are wrong.

## Decision

- **Unit tests** state the expected output for hand-written inputs, for every model with logic in it (as-of joins, deduplication, windowing).
- **Data tests** run on every build against real data: grain, keys, relationships, reconciliation to the source.
- **Deliberate breaks** (mutants) are applied to a copy of the project in CI; each must fail at least one test, and which test catches which break is recorded per engine.
- Unit tests run on the engine the project deploys with.

## Consequences

- Four of four deliberate breaks failed the build. Joining invoices to the current version passed all 46 data tests and was caught only by a unit test.
- On dbt v2 2.0.8, two unit tests missed their breaks because expected timestamps are not compared (dbt-labs/dbt#15894); the data tests still caught both. The per-engine record makes such differences visible.

## Alternatives considered

- **Data tests only.** Cheap, and blind to plausible-but-wrong logic.

## Evidence

<!-- evidence:start -->
- **4 of 4** deliberate model breaks that failed the build. Each break applied to a copy of the dbt project and built twice, with unit tests and with data tests only; recorded per engine and checked in CI. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **5,048 of 5,048** invoices on the plan they billed, Type 2 dimension from dbt snapshots. As-of join of each invoice to the dim_account version in effect at billing, scored against the generator's truth file; the dimension was built from 13 monthly snapshot loads. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- data-stack-lab [Tests that fail when they should](https://github.com/technobasant/data-stack-lab#tests-that-fail-when-they-should)
