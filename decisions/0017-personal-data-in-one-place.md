# 0017. Personal data lives in one place: facts carry keys, not identities

- Status: Accepted
- Date: 2026-10-20
- Deciders: security and compliance lead, data lead; proposed by the architect
- Evidence: dpa_erasure_model, dpa_erasure_uniform

## Context

An erasure must reach every table, copy and version within 30 days (Q10,
[0012](0012-erasure.md)). On the chosen format, Delta with UniForm
([0006](0006-open-format-in-the-clients-account.md)), there are no deletion vectors, so every
row-level change rewrites the files it touches. The event history is the largest table: 31.5
million rows today, 3.8 billion at 36 months. Where a model copies an e-mail address or a name
decides what erasing one person costs, how many places mask it
([0011](0011-tags-drive-masking-and-row-filters.md)) and how many an auditor has to check
(Q13).

## Decision drivers

- Q10: erasure everywhere inside 30 days, with a proof.
- Q13: who read personal data, answerable from few places.
- Erasure that costs the same at 36 months as today.
- Analysts rarely need an identity; customer success sometimes does.

## Options

Measured on Databricks, erasing one person (551 of 31.85 million events) by setting their
e-mail and name to NULL:

| | Files rewritten | Rows rewritten | Places to mask and audit | An analyst needs a join for an identity |
|---|---|---|---|---|
| E-mail and name copied into every event row (UniForm) | 3 of 3, the whole table | 31,849,449 | every fact | no |
| The same on plain Delta with deletion vectors | none at the update; all 3 at the purge that erasure needs | the same, deferred | every fact | no |
| **Personal columns only in `raw`, `staging` and one user table; facts carry `user_id`** | 1, in a 60,000-row table | 59,999 | one table per source, plus `raw` | yes, through a role-restricted view |
| Tokenise identities at ingestion into a separate vault | 1 row in the vault | 1 | the vault | yes, through the vault's service |

## Decision

Columns classified `personal` exist only in `raw`, in `staging` and in one identity table per
source (`users` from the product, the billing customer from Stripe). Facts and marts carry
`user_id` and `account_id`, never an identity. A CI test fails the build if any mart column is
tagged `personal`, so the rule holds when someone adds a convenient join. Customer success
reaches identities through one view, granted to its role and masked for everyone else.

Tokenisation in a vault isolates identities further, at the price of a service to run and to
keep available; for a team of two to four the identity table gives most of the benefit.

## Consequences

- Erasing a person rewrites a few small tables, not the event history, and costs the same at
  3.8 billion events as at 31 million.
- `user_id` in the facts is pseudonymous personal data while an identity table can resolve it;
  once the person's identity rows are erased, nothing in the platform links it back. That
  reading is the data protection officer's to confirm, and is written into the DPA.
- Masking, the access audit and the erasure proof each cover a handful of tables.
- An analyst who wants a name next to a usage figure joins through the restricted view, and
  the access audit records that they did.

## Revisit when

A use case needs identities at event grain (a per-user export for customers, say): it is
served as a view at read time, not a copy; or volumes of identity tables grow enough that
their rewrite cost matters, which is when a tokenisation vault earns its keep.

## Evidence

<!-- evidence:start -->
- **31,849,449 rows** rewritten to erase one person (551 events) when the model copies e-mail and name into every event row; 59,999 when they live only in a 60,000-row user table. Databricks SQL 2026.39 on Free Edition, UniForm tables (no deletion vectors) built from the proof of concept's 31.85 million events: UPDATE … SET email = NULL, full_name = NULL for one user; the wide table's 3 files were all rewritten (7.6 s), the user table's 1 file (1.1 s); on plain Delta with deletion vectors the update wrote 3 vectors and the purge then rewrote all 3 files. Source: [data-platform-architecture/results/poc-databricks-governance.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks-governance.json)
- **8 files** rewritten by deleting one user's rows from a UniForm table, which refuses deletion vectors; time travel still returned all 100 rows until the retention passed. Databricks SQL 2026.39 on Free Edition: a Delta table with delta.enableIcebergCompatV2 and Iceberg as a universal format; creating it with deletion vectors failed with DELTA_ICEBERG_COMPAT_VIOLATION.DELETION_VECTORS_SHOULD_BE_DISABLED; DELETE removed 8 files and added 1; time travel refused only after a 1-hour retention and VACUUM. Source: [data-platform-architecture/results/poc-databricks.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks.json)
<!-- evidence:end -->
