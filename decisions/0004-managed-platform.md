# 0004. A managed platform, not a self-run lakehouse

- Status: Accepted
- Date: 2026-10-19
- Deciders: CTO, CFO, data lead; proposed by the architect
- Evidence: lakehouse_rollback, lakehouse_compaction

## Context

The client has two data people, four by month six, and no one on call for a data
platform. The cost model puts every managed option inside the budget at 36 months; a
self-run lakehouse is the cheapest bill after the per-scan engines and the most expensive
option once the engineer it needs is counted ([4. Options](../docs/04-options.md)).

## Decision drivers

- People: a team of two to four, no dedicated operator.
- Cost: under $15,000 a month in year one.
- Q9, Q10, Q11, Q13: restore, erasure, row filters, masking and audit, which a managed
  platform provides and a self-run one has to build.
- Leaving later: data in open formats in the client's account.

## Options

| | Team of two to four | Bill at 36 months | With operations | Governance built in | Open format |
|---|---|---|---|---|---|
| **Managed platform (Databricks or Snowflake)** | ✔ | $1,476–3,081 | $2,576–4,731 | ✔ | ◐ by configuration |
| AWS-native, assembled (Athena, Glue, Lake Formation) | ◐ | $55 | $2,805 | ◐ | ✔ |
| Self-run Iceberg, catalog and Trino on Kubernetes | ✘ about one engineer full time | $697 | $11,697 | ✘ | ✔ |

Figures from [`results/cost.json`](../results/cost.json), on list prices and the stated
assumptions.

## Decision

The platform is managed: Databricks or Snowflake, chosen by
[0005](0005-databricks-or-snowflake.md), with the AWS-native option as the control in that
comparison. Nothing distributed is self-run in year one.

## Consequences

- The vendor bill is the main cost, and it grows with use: budgets, alerts and per-team
  attribution are part of stage 1 ([9. Operations](../docs/09-operations.md)).
- The labs' self-run designs (Iceberg with vended credentials, snapshot rollback,
  compaction) remain the reference for what the managed platform must match, and the exit
  path if the vendor's terms change.
- Reversible at a migration's cost, kept low by keeping tables in an open format
  ([0006](0006-open-format-in-the-clients-account.md)).

## Revisit when

The platform bill passes $15,000 a month with usage that is not waste, or the team grows
past eight with someone who wants to own a query engine.

## Evidence

<!-- evidence:start -->
- **909,968** rows recovered by snapshot rollback. An over-broad DELETE (a WHERE reaching years further back than intended), then ALTER TABLE EXECUTE rollback_to_snapshot, counted against the pre-incident total. Source: [lakehouse-lab/MEASUREMENTS.md](https://github.com/technobasant/lakehouse-lab/blob/main/MEASUREMENTS.md)
- **20 → 1** files merged per partition by optimize. Twenty 5,000-row inserts into one partition, then ALTER TABLE EXECUTE optimize, counted from the $files metadata table. Source: [lakehouse-lab/MEASUREMENTS.md](https://github.com/technobasant/lakehouse-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
