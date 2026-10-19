# 7. Security and governance

The rules a pipeline cannot route around: who owns each dataset, who may read what, what
happens to personal data, and the evidence an auditor gets. Written for the SOC 2 Type II
window that opens in month three and the erasure commitment in the data processing
agreement ([the brief](01-brief.md#constraints)).

## Ownership

| Dataset | Owner | Contract |
|---|---|---|
| The product's tables (CDC) | product engineering | [`product-database`](../models/contracts/product-database.odcs.yaml) |
| Stripe export | finance systems | [`stripe-billing`](../models/contracts/stripe-billing.odcs.yaml) |
| Marts | the data team | [`usage-mart`](../models/contracts/usage-mart.odcs.yaml) and the dbt contracts |

A dataset with no owner is not read by a dashboard. Contracts are checked in the producer's
CI ([0013](../decisions/0013-contracts-at-the-producer.md)).

## Classification

| Class | Examples | Where it may appear | Who reads it |
|---|---|---|---|
| Public | plan names, prices | anywhere | anyone with access |
| Internal | usage counts, plan history, account ids | marts | every analytical role |
| Confidential | account names, per-account revenue | marts, masked except for named roles | finance, customer success |
| Personal | e-mail addresses, names, billing e-mail | `raw` and `staging` only | the platform team; erasure jobs |

Every column's class is set in its contract or dbt model and applied as a catalog tag by
the build. Masking policies attach to tags, so a new personal column is masked the day it
ships ([0011](../decisions/0011-tags-drive-masking-and-row-filters.md)).

## Access

- **People** come from the client's identity provider by SCIM, into groups; groups map to
  roles; nobody is granted a table directly.
- **Roles:** `analyst` (marts, internal), `finance` (plus confidential revenue),
  `customer_success` (plus confidential account names), `platform` (all zones),
  `bi_service` (the BI tool, with each viewer's role passed through where the tool allows),
  `usage_reader` and `assistant` (customer-facing, always under a row filter on
  `account_id`).
- **Jobs** run as service principals, one per pipeline, so the audit log names the job.
- **Storage** is reached only through the platform's catalog; nobody holds S3 keys to the
  table bucket.
- **Tenant isolation** is a row filter on `account_id` for every role that acts for a
  customer, and a CI test per path: as account A, a query for account B returns nothing.

## Personal data: retention and erasure

| Zone | Retention | On an erasure request |
|---|---|---|
| `raw` | 25 months | rows deleted by `user_id` and by the user's e-mail, within 7 days |
| `staging` | rebuilt | gone on the next build |
| `history`, `marts` | indefinitely | no personal columns; the user's id is kept, unlinked from any identifier |
| Table versions | 7 days ([0015](../decisions/0015-restore-points.md)), plus any vendor fail-safe | expire on schedule; set so nothing survives day 30 |
| Old S3 dumps of deleted events | deleted once the platform holds the history | |

An erasure is done when the proof query, run after day 30, finds no identifier of the
person in any table or reachable version, and its result is stored in `audit`
([0012](../decisions/0012-erasure.md)). Measured on both platforms in the proof of concept.

## SOC 2 and GDPR: what the platform provides

| Requirement | Control | Evidence the auditor gets |
|---|---|---|
| SOC 2 CC6.1, logical access | roles by group; catalog-only access to storage; row filters for customer-facing paths | role and grant export from Terraform; isolation test results |
| SOC 2 CC6.2, CC6.3, provisioning and removal | SCIM from the identity provider; quarterly access review | SCIM log; review sign-off |
| SOC 2 CC7.2, monitoring | query and access history retained in `audit` | the Q13 query: who read personal or confidential data, by person and job |
| SOC 2 CC8.1, change management | Terraform for platform objects; dbt in Git with CI; contracts checked in producers' CI | merged pull requests with passing checks |
| SOC 2 C1.2, disposal | retention by zone; version expiry | lifecycle rules and retention settings in Terraform |
| GDPR Art. 17, erasure | delete by key, expiry inside 30 days, proof query | stored proof per request |
| GDPR Art. 30, records of processing | contracts with purpose, classification and owner | the contracts |
| GDPR Art. 32, security of processing | encryption with the client's KMS key; private connectivity; least privilege | Terraform; key policy |

## Lineage

The platform's catalog records table- and column-level lineage for jobs it runs; dbt adds
model lineage. Lineage turns "this source column changed" into a list of affected marts and
dashboards, which is what the contract check uses to name the consumers to ask.
