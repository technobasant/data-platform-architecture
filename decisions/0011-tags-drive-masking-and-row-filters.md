# 0011. Classification tags drive masking and row filters; every table carries the account

- Status: Proposed
- Date: 2026-10-19
- Deciders: security and compliance lead, data lead; proposed by the architect
- Evidence:

## Context

Today one database login reads everything, and isolation between customers exists only in
the product's application code. The platform will be read by analysts, finance, the BI
tool, the usage page in stage 2 and the assistant in stage 3, and SOC 2 needs access
reviewed and logged. Grants written table by table drift as tables are added.

## Decision drivers

- Q11: no path open to a customer returns another account's rows.
- Q13: who read personal or confidential data, answered from logs.
- Personal data out of what analysts read, unless a use case is approved.
- Works the same on Databricks and Snowflake.

## Options

| | Q11 isolation | New tables covered without new grants | Auditable | Portable |
|---|---|---|---|---|
| Grants per table and per role | ◐ | ✘ | ◐ | ✔ |
| Separate copies per audience (a masked mart, a per-customer view) | ◐ | ✘ | ◐ | ✔ |
| **Column tags set in the model's contract; tag-based masking policies; a row filter on the account key, applied by policy** | ✔ | ✔ | ✔ | ◐ same design, two syntaxes |

## Decision

Proposed until the proof of concept measures it (criterion 3 of
[0005](0005-databricks-or-snowflake.md)):

- Every column is classified in the dbt model's YAML (public, internal, confidential,
  personal); the build applies the tag in the catalog.
- Masking policies attach to tags, not to columns, so a new personal column is masked the
  day it ships.
- Every table that holds customer data carries `account_id`, and a row filter on it is
  applied to every role that acts for a customer (the usage page, exports, the assistant).
- People get roles, not grants; roles map to zones and classes
  ([7. Security and governance](../docs/07-security-and-governance.md)).

## Consequences

- The isolation tests become part of CI: for each customer-facing path, a query as one
  account must return nothing of another's.
- On Snowflake this needs Enterprise edition; on Databricks, Unity Catalog on a Premium
  workspace.
- A wrong tag is a wrong policy: tags are reviewed with the contract.

## Revisit when

The proof of concept completes; then Accepted with the isolation test results as evidence.

## Evidence

<!-- evidence:start -->
Not measured yet; see the status above.
<!-- evidence:end -->
