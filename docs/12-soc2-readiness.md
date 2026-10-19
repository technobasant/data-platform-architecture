# 12. SOC 2 readiness

What SOC 2 actually checks, what this engagement puts in scope, and the controls that
produce the evidence an auditor asks for. Built on
[7. Security and governance](07-security-and-governance.md); not a repeat of it.

## What SOC 2 is

SOC 2 is an attestation report, issued by a licensed CPA firm, against the AICPA's Trust
Services Criteria (the 2017 criteria, with points of focus revised in 2022). It is not a
certification and not a law: it is an independent opinion that a service organisation's
controls are designed (**Type I**, a point in time) or designed and operating effectively
(**Type II**, over a period, typically three to twelve months) against the criteria it
chooses to be assessed on.

The brief's timeline: the audit window opens in month three, and the report is due in month
nine ([1. Brief](01-brief.md#why-now)) — a six-month Type II period, at the short end of
what is typical, because two enterprise prospects are waiting on it.

## Scope

[0018](../decisions/0018-soc2-scope.md) decides this:

- The analytical platform is **inside** the client's system description from the day it
  holds customer data, alongside the product itself.
- **Security** (the common criteria), **Availability** and **Confidentiality** are in scope.
  **Processing integrity** is out: revenue reporting is read by people, not acted on
  automatically, so there is no automated processing whose integrity a customer depends on
  yet; this is revisited if billing is ever computed from platform data.
  **Privacy** is out of the SOC 2 report specifically: it is handled under the GDPR
  programme and the data processing agreement instead
  ([7. Security and governance](07-security-and-governance.md#gdpr-what-the-platform-provides)),
  since Privacy as a Trust Services Criterion would duplicate that work inside a second
  framework for no requirement anyone has asked for.
- **Vendors are carved out.** AWS and the platform vendor (Databricks or Snowflake) are
  outside the system description; their own SOC 2 Type II reports are obtained and reviewed
  every year, and the complementary user entity controls each report lists — the things the
  vendor's control only works if the customer also does — are mapped to the client's own
  controls below (CC9.2). Stripe is a vendor too, under the same vendor-management control,
  not a system this report's boundary reaches into.

## Timeline

Aligned with [10. Roadmap](10-roadmap.md):

- **Before the window opens (month 3):** stage-0 controls on the replica — personal roles
  replacing the shared login, query logging — are in place in weeks 0–2, specifically so
  they are already operating when the window opens, not started to meet it.
- **Before the platform holds customer data (wave 1, week 10):** platform controls
  (Terraform-managed access, tagging, logging) exist from the day the platform is created,
  empty and governed, in weeks 6–10 — before wave 1 loads a single customer row.
- **Controls added mid-period** (through waves 2–4, weeks 16–26) are tested by the auditor
  from their own start date, not from month three: a control that started operating in
  month 5 is evaluated over four months of the six-month window, not six.

## The control matrix

Roughly twenty controls, not the maximum the criteria allow: chosen because they map to
something this platform already does or measures, not added to pad the matrix.

| Control id | Criterion | Control | How the platform implements it | Evidence | How it is collected | Owner | Frequency |
|---|---|---|---|---|---|---|---|
| PLAT-01 | CC2.1 | A data-handling standard exists and is followed | every contract column carries a classification; the data model and glossary are published documents ([6. Data model](06-data-model.md)) | the contracts; the published docs | automated: contracts linted in CI | data owner | per change |
| PLAT-02 | CC3.2 | Risk is identified and reviewed | the risk register, rated and owned, with a trigger to act ([risks.md](risks.md)) | risks.md, with a dated review note | manual: quarterly review | CTO | quarterly |
| PLAT-03 | CC6.1 | Logical access is by role, not grant | SCIM groups map to roles; no table is granted to a person directly; storage is reached only through the catalog; encryption at rest with the client's own KMS key ([7. Security and governance](07-security-and-governance.md#access)) | Terraform's role and grant export; the KMS key policy | automated: nightly export to the evidence bucket | platform team | continuous; reviewed monthly |
| PLAT-04 | CC6.2 | Provisioning needs the owner's approval | confidential or personal access is requested and approved before the grant is made ([Access lifecycle](07-security-and-governance.md#access-lifecycle)) | the request and approval record from the identity provider | automated: IdP audit log export | data owner | per request |
| PLAT-05 | CC6.3 | Access is removed, and reviewed | SCIM deprovisioning removes a leaver's roles within a day; every owner re-confirms every grant quarterly | the SCIM deprovisioning log; the review sign-off | automated collection; manual sign-off | data owner | continuous; reviewed quarterly |
| PLAT-06 | CC6.6 | The network is segmented | CDC reaches RDS over the client's VPC, never the public internet; PrivateLink is priced as an option ([4. Options](04-options.md#cost)) | the VPC routing configuration in Terraform | automated: Terraform state | platform team | per change |
| PLAT-07 | CC6.7 | Data is encrypted in transit | TLS is enforced on every platform connection: CDC, the BI tool, the Terraform provider | the TLS configuration in Terraform | automated: Terraform state | platform team | continuous |
| PLAT-08 | CC6.8 | Dependencies are pinned and scanned | CI pins every dependency (`uv.lock`, pinned Terraform providers) and scans for known vulnerabilities before a merge | the CI scan output | automated: CI job per PR | platform team | per change |
| PLAT-09 | CC7.1 | Configuration drift is detected | a nightly `terraform plan` against production catches a console change before it is mistaken for intended; Terraform is also scanned for policy violations in CI | the nightly plan output (no changes expected); the policy scan report | automated: scheduled job, CI job | platform team | nightly |
| PLAT-10 | CC7.2 | Access to sensitive data is monitored | the Q13 audit query names every reader of a personal or confidential column; the break-glass role and repeated failed logins alert immediately ([The access audit (Q13)](07-security-and-governance.md#the-access-audit-q13)) | the audit query's result; the alert log | automated: scheduled query, identity-provider alerting | security lead | reviewed quarterly; alerts continuous |
| PLAT-11 | CC7.3 | Incidents are handled by a runbook | each failure mode has a runbook: a CDC slot stalling, a bad write, a quality gate holding a day ([9. Operations](09-operations.md#runbooks)) | the incident ticket, with the runbook followed | manual, logged per incident | data lead | per incident |
| PLAT-12 | CC7.4 | Incidents are reviewed afterwards | a Sev1 or Sev2 incident ([Data quality management](07-security-and-governance.md#data-quality-management)) gets a post-incident note: cause, fix, whether it recurs | the post-incident review note | manual | data lead | per incident |
| PLAT-13 | CC7.5 | The platform recovers from a security incident | affected tables restored to the version before the incident (0015); the credentials of every principal involved rotated; customers told as the DPA requires | the incident record, with the restore and rotation steps | manual, logged per incident | security lead | per incident |
| PLAT-14 | CC8.1 | Changes go through review | every dbt, contract and Terraform change merges through a reviewed pull request with CI passing; a console change is drift, caught by PLAT-09 | the merged PR and its checks | automated: CI status on the PR | platform team | per change |
| PLAT-15 | CC9.1 | A disaster recovery plan exists | component-by-component RTO and RPO, by failure mode ([13. Quality attributes](13-quality-attributes.md#disaster-recovery)) | the DR plan, version-controlled | manual, reviewed | CTO | reviewed annually |
| PLAT-16 | CC9.2 | Vendor reports are reviewed | AWS's and the platform vendor's SOC 2 Type II reports, and the complementary user entity controls each requires, are reviewed every year ([Scope](#scope)) | the vendor report and the review note | manual | security lead | annually |
| PLAT-17 | A1.1 | Capacity is planned and budgeted | warehouse sizing projected to 36 months; spend alerts at 50%, 80% and 100% of pro-rata budget; the measured bill ([11. Proof of concept](11-proof-of-concept.md#cost-what-the-billing-table-charged)) | the budget alert configuration; the billing export | automated: nightly billing export | data lead | continuous |
| PLAT-18 | A1.2 | Backups exist and are current | table versions kept 7 days; an off-account backup kept 14 days ([0015](../decisions/0015-restore-points.md)) | the backup job log; the vault inventory | automated | platform team | continuous |
| PLAT-19 | A1.3 | Restores are tested | a quarterly restore drill against Q9's one-hour target | the timed drill record | manual drill | platform team | quarterly |
| PLAT-20 | C1.1 | Data is classified before it is confidential by accident | classification comes from the contract, not an afterthought; CI fails the build on an unclassified column | the CI run log; the contract | automated: CI job per PR | data owner | per change |
| PLAT-21 | C1.2 | Data is disposed of on schedule | retention by zone ([Retention schedule](07-security-and-governance.md#retention-schedule)); landed files expire at 30 days; an erasure proof is stored per request ([0012](../decisions/0012-erasure.md)) | the lifecycle rule configuration; the stored erasure proof | automated lifecycle rules; the proof query's result stored per request | platform team | continuous |

## Evidence that collects itself

A nightly job writes to an evidence bucket in a separate AWS account, with object lock so a
written record cannot be altered or deleted before its retention passes
([Retention schedule](07-security-and-governance.md#retention-schedule)):

- grant and group snapshots, from Terraform state and the identity provider;
- the Q13 audit query's result;
- access review sign-offs, as they are confirmed;
- restore drill records, timed;
- CI and PR records for changes merged that day;
- vendor report reviews, as they happen (annually, so most nights write nothing here).

Evidence names staff — the reader of a column, the approver of a grant — never a customer's
end user. A customer's own personal data does not belong in evidence of how it was
protected.

## What an auditor asks, and the answer

- **"Who read personal data last quarter?"** Run the Q13 query
  ([7. Security and governance](07-security-and-governance.md#the-access-audit-q13)); point
  at the quarter's stored result in the evidence bucket, not a fresh run during the audit.
- **"Show me a leaver who was removed."** The SCIM deprovisioning log entry, timestamped
  within a day of the HR system marking them a leaver, and the role export showing their
  groups empty afterwards.
- **"Show me a change to the platform."** The merged pull request: the diff, the CI checks
  that passed, the reviewer's approval.
- **"Show me a restore."** The timed drill record from the quarterly rehearsal: the table,
  the version restored to, the time it took, against the one-hour target (Q9).
- **"Show me a vendor review."** The platform vendor's or AWS's SOC 2 Type II report for the
  year, and the review note mapping its complementary user entity controls to this matrix.
- **"Show me a quality incident and what happened after it."** The incident ticket, the
  runbook followed, and the post-incident note (PLAT-11, PLAT-12).

## Where SOC 2 programmes usually fail

Not on the controls that are hard to design — on the ones nobody kept operating:

- **Access reviews run late**, or not at all, once the person who used to do them leaves.
  The quarterly cadence here is sized for a team of two to four on purpose, so it is a
  30-minute task, not a project.
- **Console changes** nobody remembers making, found by the auditor before they are found by
  `terraform plan`. The nightly drift check exists to find them first.
- **Restores are never actually tried** until the day one is needed, which is the worst day
  to discover the backup does not restore. The quarterly drill is timed and recorded
  precisely so "we have backups" is never asserted without "and we tried one."
- **Vendor reports are filed, not read.** A vendor's SOC 2 report lists complementary
  controls the customer must run for the vendor's controls to mean anything; an unread
  report is a control gap wearing a compliance document's clothes.
- **Evidence gathered by hand, at the end**, reconstructed from memory and screenshots in
  the week before the auditor arrives. The nightly job above is the alternative: evidence
  that exists because the control ran, not because someone remembered to document it.

---

[← 11. Proof of concept](11-proof-of-concept.md) · [README](../README.md) · [13. Quality attributes →](13-quality-attributes.md)
