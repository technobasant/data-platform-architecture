# 0011. Classification tags drive masking and row filters; every table carries the account

- Status: Proposed
- Date: 2026-10-19
- Deciders: security and compliance lead, data lead; proposed by the architect
- Evidence: dpa_tag_masking, dpa_row_filter_identity, dpa_session_variable_filter

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

Proposed until both halves of the proof of concept have measured it (criterion 3 of
[0005](0005-databricks-or-snowflake.md)); the Databricks half is in
[11. Proof of concept](../docs/11-proof-of-concept.md):

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
- On Snowflake this needs Enterprise edition; on Databricks, Unity Catalog with a governed
  tag (a tag policy), which attribute-based policies require.
- Measured on Databricks: one schema-level policy masked every personal column from the
  contract and a personal column on a table created after the policy, with nothing but its
  tag set; a row filter on the caller's identity scoped a table to one account.
- Also measured on Databricks: a row filter cannot read a session variable, so a service
  acting for many customers (the stage-3 assistant) cannot pass the customer per request
  into the policy. The assistant's tool scopes its queries instead
  ([AI architecture, 0011](https://github.com/technobasant/ai-platform-architecture/blob/main/decisions/0011-identity-on-the-platform.md)).
- A wrong tag is a wrong policy: tags are reviewed with the contract.

## Revisit when

The proof of concept completes; then Accepted with the isolation test results as evidence.

## Evidence

<!-- evidence:start -->
- **3 of 3** personal columns masked by one policy on the classification tag, including a column on a table created after the policy. Databricks SQL 2026.39 on Free Edition: a governed tag `class`; the product contract's four tables created and all 26 columns tagged from the contract; one schema-level column-mask policy matching has_tag_value('class', 'personal'); every non-personal column stayed readable. Source: [data-platform-architecture/results/poc-databricks.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks.json)
- **1 of 5** accounts visible through a row filter keyed to the caller's identity. A row filter on account_id that admits the accounts mapped to current_user() in a mapping table; moving the mapping moved the scope to the other account. Source: [data-platform-architecture/results/poc-databricks.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks.json)
- **UNRESOLVED_COLUMN** what Databricks returns for a row filter function that reads a session variable: a per-request value cannot scope rows. DECLARE VARIABLE request_account, then CREATE FUNCTION … RETURN account_id = request_account, on Databricks SQL 2026.39. Source: [data-platform-architecture/results/poc-databricks.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks.json)
<!-- evidence:end -->
