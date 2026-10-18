# 0013. A managed warehouse or lakehouse platform is chosen per workload, with the cost model and the team in view

- Status: Proposed. The open-table design is measured in the labs; the managed platforms are modelled from list prices, not yet measured.
- Date: 2026-10-18
- Evidence:

## Context

Snowflake, Databricks, BigQuery and an open lakehouse on object storage can all serve the analytical layer. They differ less in what they can do than in how they charge, what they make easy, and what a team already knows.

## Decision

- The open tables of [0002](0002-open-tables-scoped-credentials.md) remain the system of record, so a managed engine can be added or replaced without moving data.
- The engine for each workload is chosen with the [platform selection guide](../docs/platform-selection.md) and the [cost model](../cost/), using the workload's own volumes, not a vendor benchmark.

## Consequences

- No lock-in at the storage layer; some lock-in at the SQL and governance layer, whichever engine is chosen.
- Cost comparisons are only as good as the workload profile and the compute-equivalence assumption, which the guide states openly.

## Alternatives considered

- **Pick one platform for everything up front.** Simpler to govern; every workload pays that platform's pricing shape.

## Evidence

<!-- evidence:start -->
Not measured yet; see the status above.
<!-- evidence:end -->
