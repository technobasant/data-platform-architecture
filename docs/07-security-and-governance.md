# 7. Security and governance

The rules a pipeline cannot route around: who owns each dataset, who may read what, what
happens to personal data, and the evidence an auditor gets. Written for the SOC 2 Type II
window that opens in month three and the erasure commitment in the data processing
agreement ([the brief](01-brief.md#constraints)). The SOC 2 control matrix itself is in
[12. SOC 2 readiness](12-soc2-readiness.md); this document is what the controls are built
on.

## Ownership

| Dataset | Owner | Contract |
|---|---|---|
| The product's tables (CDC) | product engineering | [`product-database`](../models/contracts/product-database.odcs.yaml) |
| Stripe export | finance systems | [`stripe-billing`](../models/contracts/stripe-billing.odcs.yaml) |
| Marts | the data team | [`usage-mart`](../models/contracts/usage-mart.odcs.yaml) and the dbt contracts |

A dataset with no owner is not read by a dashboard. Contracts are checked in the producer's
CI ([0013](../decisions/0013-contracts-at-the-producer.md)).

## Operating model

Five roles, not five people — on a team of two to four, one person often holds two:

- **Data owner.** Accountable for a domain: product engineering for the product's tables,
  finance systems for Stripe, the data team for marts and derived products
  ([6. Data model](06-data-model.md#domains-and-data-products)). Approves what the contract
  classifies, who gets confidential or personal access, and whether a breaking change ships.
- **Data steward.** The person who does the day-to-day work of keeping a domain's data
  correct: triages quality incidents, processes access requests, keeps the glossary entry
  current. Usually the analytics engineer, rotating by domain.
- **Platform team (custodian).** Runs the catalog, the policies and the Terraform that
  implement what owners and stewards decide. Holds no personal opinion on who should read
  what; executes the decision and produces the evidence.
- **Producer team.** Whoever writes the source system (product engineering for the
  database, finance systems for Stripe). Proposes classification and schema changes in the
  contract; does not grant access to the platform.
- **Consumer.** Analysts, finance, customer success, the BI tool's service identity, the
  stage-3 assistant. Requests access and states a freshness need; does not set policy.

### RACI

| Activity | Data owner | Data steward | Platform team | Producer team | Consumer |
|---|:-:|:-:|:-:|:-:|:-:|
| Classifying a column | A | C | C | R | I |
| Approving access to confidential or personal data | A | R | C | I | I |
| Approving a breaking contract change | A | C | C (confirms consumers via lineage) | R | I (acknowledges) |
| Setting a freshness objective | A | C | I | I | R |
| Handling a quality incident | A | R | C | C (if source-caused) | I |
| Running an erasure | I | A (confirms the proof) | R | I | — |
| The quarterly access review | R/A | C | C (produces the export) | I | I |
| Changing retention | A | C | R | I | I |

R = does the work, A = accountable (one per row), C = consulted, I = informed.

### Cadence

Sized for a team of two to four, not a compliance department:

- **Weekly, 30 minutes.** Data triage: held days, failing tests, open access requests, any
  isolation-test failure. Data steward and platform team.
- **Monthly.** Owner review: each data owner reads the data-quality scorecard
  ([below](#data-quality-management)) for their domain and signs off, or opens an incident.
- **Quarterly.** Access review: every owner re-confirms every grant into confidential or
  personal data in their domain ([Access lifecycle](#access-lifecycle)).

## Classification

| Class | Examples | Zones allowed | Default masking | Export allowed | Retention | Reads logged and reviewed |
|---|---|---|---|---|---|---|
| Public | plan names, prices | any | none | anywhere | indefinite | not logged specially |
| Internal | usage counts, plan history, account ids | marts and above | none | within the company (the BI tool, the board pack) | 25 months (event-grain facts) or indefinite (dimensions) | job-level query history only |
| Confidential | account names, per-account revenue | marts, masked except named roles | masked unless the reader's role is `finance` or `customer_success` | no external export without the data owner's approval | as above | logged; reviewed at the monthly owner review |
| Personal | e-mail addresses, names, billing e-mail | `raw`, `staging`, one identity table per source ([0017](../decisions/0017-personal-data-in-one-place.md)) | masked for every role except the identity view's grantees (`customer_success`, through `cs_user_contacts`) | never exported | while the account is active; erased on request | every read logged through column lineage; the Q13 query reviews it quarterly ([below](#the-access-audit-q13)) |

Every column's class is set in its contract or dbt model and applied as a catalog tag by
the build. Masking policies attach to tags, so a new personal column is masked the day it
ships ([0011](../decisions/0011-tags-drive-masking-and-row-filters.md)).

## Catalog and glossary

The platform's catalog (Unity Catalog, or Snowflake's equivalent) is the system of record
for every table: its owner, its classification tags and its description. It is not a wiki
page that drifts from the schema; the tags the catalog shows are the tags the mask and row
filter policies read.

The glossary is the metric definitions in
[6. Data model](06-data-model.md#glossary-of-metrics): active user, active account, events,
MRR or revenue by plan, plan change types. It is the same glossary the stage-3 assistant's
semantic layer uses, quoted where that layer defines a term, so a customer and an analyst
asking the same question get the same number.

A **certified** tag marks a mart as ready for a dashboard: it has an owner, a contract, data
tests that pass, and a described glossary entry. The BI tool's dashboards are built only on
certified marts; a dashboard on an uncertified table is a governance gap to close, not a
feature to ship around.

## Access

- **People** come from the company's identity provider by SCIM, into groups; groups map to
  roles; nobody is granted a table directly.
- **Roles:** `analyst` (marts, internal), `finance` (plus confidential revenue),
  `customer_success` (plus confidential account names, and `cs_user_contacts`),
  `platform` (all zones), `bi_service` (the BI tool, with each viewer's role passed through
  where the tool allows), `usage_reader` and `assistant` (customer-facing, always under a
  row filter on `account_id`).
- **Jobs** run as service principals, one per pipeline, so the audit log names the job.
- **Storage** is reached only through the platform's catalog; nobody holds S3 keys to the
  table bucket.
- **Tenant isolation** is a row filter on `account_id` for every role that acts for a
  customer, and a CI test per path: as account A, a query for account B returns nothing.

## Access lifecycle

1. **Request.** A person requests a role, not a table, through the identity provider's
   access catalogue, naming the business reason.
2. **Approval.** Internal access needs no per-request approval: it is in the standard
   analyst role. Confidential or personal access needs the data owner's approval.
3. **Grant.** Personal-data access is time-boxed and expires on its own (90 days); it is
   never a standing grant renewed by habit — a lapsed grant is requested again, with a
   reason again.
4. **Quarterly review.** Each data owner re-confirms every grant into their domain's
   confidential or personal data. An unconfirmed grant is revoked, not left pending.
5. **Leavers.** SCIM deprovisioning removes a person's group membership within a day of HR
   marking them a leaver, which removes every role that membership mapped to, at once.
6. **Jobs.** One service principal per pipeline, scoped to only the schemas it reads or
   writes — never a personal login running a scheduled job.
7. **Break-glass.** One role for an emergency that bypasses the normal path. Every use
   alerts the security lead immediately and is reviewed within a day; it is not a
   convenience account.

## Personal data: retention and erasure

| Zone | Retention | On an erasure request |
|---|---|---|
| `raw` | 25 months | rows deleted by `user_id` and by the user's e-mail, within 7 days |
| `staging` | rebuilt | gone on the next build |
| identity table (`stg_users`, `stg_billing_customer`) | while the account is active | erased by key within 7 days; this is the one place in `history`/`marts` territory personal columns are allowed to be, and the one place erasure has to reach beyond `raw` ([0017](../decisions/0017-personal-data-in-one-place.md)) |
| `history`, `marts` (everywhere else) | indefinitely | no personal columns; the user's id is kept, unlinked from any identifier |
| Table versions | 7 days ([0015](../decisions/0015-restore-points.md)), plus any vendor fail-safe | expire on schedule; set so nothing survives day 30 |
| Old S3 dumps of deleted events | deleted once the platform holds the history | |

Where a model keeps personal data decides what erasing one person costs, not just whether it
is possible. Measured on Databricks, erasing one person (551 events) rewrote **31,849,449
rows** when a model copied their e-mail and name into every event row, and **59,999** when
they lived only in a 60,000-row user table
([`results/poc-databricks-governance.json`](../results/poc-databricks-governance.json),
[0017](../decisions/0017-personal-data-in-one-place.md)). That is why personal columns are
confined to `raw`, `staging` and the identity table, and why the rule is a CI test rather
than a convention: a mart column tagged `personal` fails the build.

An erasure is done when the proof query, run after day 30, finds no identifier of the
person in any table or reachable version, and its result is stored in `audit`
([0012](../decisions/0012-erasure.md)). Measured on both platforms in the proof of concept.

## Retention schedule

Every dataset's retention, not personal data alone:

| What | Retention | Mechanism |
|---|---|---|
| Landed files (S3) | 30 days | S3 lifecycle rule ([0003](../decisions/0003-files-immutable-loads-by-key.md)) |
| Raw CDC log and loaded-file tables | 25 months; personal data erased by key sooner, on request | table retention plus the erasure job ([0002](../decisions/0002-cdc-from-the-product-database.md), [0012](../decisions/0012-erasure.md)) |
| `staging` | not separately retained | rebuilt on every run |
| `history` and `marts`: event-grain facts | 25 months, matching `raw` | table retention |
| `history` and `marts`: dimensions, `fct_invoices` | indefinitely | no expiry; erasure by key only |
| Identity tables (`stg_users`, `stg_billing_customer`) | while the account is active | erasure job ([0012](../decisions/0012-erasure.md), [0017](../decisions/0017-personal-data-in-one-place.md)) |
| Table versions (time travel) | 7 days ([0015](../decisions/0015-restore-points.md)) | the table format's own retention setting |
| Off-account backups | 14 days | AWS Backup vault, separate account ([0015](../decisions/0015-restore-points.md)) |
| Platform audit and lineage records | exported nightly to the evidence bucket | the platform's own system tables keep a limited window, which is the vendor's to state and has to be checked against its documentation, not assumed |
| SOC 2 evidence | the audit period plus one year | the evidence bucket, with object lock ([12. SOC 2 readiness](12-soc2-readiness.md)) |

## Data quality management

**Objectives per data product**, measured by the quality gates
([0014](../decisions/0014-quality-gates.md)):

- **Freshness:** yesterday complete by 06:00 UTC, 29 days in 30 (Q5).
- **Completeness:** each day's row count checked against the source's own count — CDC
  tables against the replica, files against the producer's manifest.
- **Validity:** contract and row tests on every delivered row.
- **Reconciliation:** revenue to the Stripe export, to the cent (Q3).

**Severity and response:**

| Severity | What it covers | Response |
|---|---|---|
| Sev1 | a mart a customer-facing path or finance depends on is wrong or stale past its objective | fixed the same business day; the data lead is paged |
| Sev2 | an internal mart held by a quality gate | fixed the next business day |
| Sev3 | a cosmetic or non-blocking issue | queued at the weekly triage, fixed within the week |

**Monthly scorecard**, one page per data product, reviewed at the monthly owner review:
freshness hit rate, days held by a gate, reconciliation variance, and access-review status.

## Policy as code

Tags, masks, row filters and grants are declared in Terraform, not set by hand in the
platform's console. Measured on Databricks: Terraform owned 6 of 7 kinds of governance
object from an empty state — the governed tag, schema, table, column tags, the tag-matching
mask policy, and grants — with a clean plan after applying
([11. Proof of concept](11-proof-of-concept.md#operability-what-terraform-can-own),
[0011](../decisions/0011-tags-drive-masking-and-row-filters.md)). The seventh, the mask
function the policy calls, has no Terraform resource on Databricks and needs a SQL step
before the policy that depends on it can apply; a change to the function is reviewed like a
change to the policy, not treated as exempt from review because it sits outside Terraform.

## The access audit (Q13)

The question the auditor asks: who read personal or confidential data, when, and through
what. Answered from the catalog's tags joined to the platform's own column lineage, not
from a shared login's absence of an answer. The query
([`poc/databricks/governance.py`](../poc/databricks/governance.py)'s `audit()`):

```sql
WITH personal AS (
    SELECT concat_ws('.', catalog_name, schema_name, table_name) AS table_name, column_name
    FROM workspace.information_schema.column_tags
    WHERE tag_name = 'class' AND tag_value = 'personal'
)
SELECT l.created_by, coalesce(l.entity_type, 'SQL query') AS through,
       p.table_name, p.column_name, COUNT(*) AS reads,
       MIN(l.event_time) AS first_read, MAX(l.event_time) AS last_read
FROM system.access.column_lineage AS l
JOIN personal AS p
  ON l.source_table_full_name = p.table_name AND l.source_column_name = p.column_name
WHERE l.event_time >= current_timestamp() - INTERVAL 90 DAYS
GROUP BY ALL
ORDER BY reads DESC
```

Measured: **5 of 5** columns tagged personal had every read in the last 90 days found by
this one query — by reader, column and time — answered in **4.7 s**, readers pseudonymised
in the result
([`results/poc-databricks-governance.json`](../results/poc-databricks-governance.json),
[0018](../decisions/0018-soc2-scope.md)). The reads it found include `users.email` and
`users.full_name`, columns the masking policy ([0011](../decisions/0011-tags-drive-masking-and-row-filters.md))
masks for most readers: lineage records the column a query referenced, not the value it
returned, so a read is in the audit even when the reader saw `***`.

## GDPR: what the platform provides

SOC 2 controls, the matrix, the evidence and how it is collected are in
[12. SOC 2 readiness](12-soc2-readiness.md). The GDPR rows stay here, since they answer the
data processing agreement directly rather than an attestation:

| Requirement | Control | Evidence the auditor gets |
|---|---|---|
| GDPR Art. 17, erasure | delete by key, expiry inside 30 days, proof query | stored proof per request |
| GDPR Art. 30, records of processing | contracts with purpose, classification and owner | the contracts |
| GDPR Art. 32, security of processing | encryption with the company's KMS key; private connectivity; least privilege | Terraform; key policy |

## Lineage

The platform's catalog records table- and column-level lineage for jobs it runs; dbt adds
model lineage. Lineage turns "this source column changed" into a list of affected marts and
dashboards, which is what the contract check uses to name the consumers to ask, and what the
access audit above uses to name who read a personal column, regardless of which mart,
staging model or raw table the read went through.

---

[← 6. Data model](06-data-model.md) · [README](../README.md) · [8. Migration →](08-migration.md)
