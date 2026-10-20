# 0018. SOC 2: the platform inside the system description, vendors carved out, three criteria

- Status: Accepted
- Date: 2026-10-20
- Deciders: CTO, security and compliance lead; proposed by the architect
- Evidence: dpa_audit_query, dpa_terraform_coverage

## Context

Two enterprise prospects asked for a SOC 2 Type II report ([the brief](../docs/01-brief.md)),
and the audit window opens in month three. The platform will hold a copy of every customer's
data. A SOC 2 report covers the system its description scopes; if customer data flows to a
platform outside that scope, the report does not cover where the data goes, and a customer's
security review will find it. The platform runs on vendors (AWS, and Databricks or Snowflake)
whose own controls the company's auditor cannot test.

## Decision drivers

- Q13: who read personal or confidential data, answerable from logs.
- The audit window in month three, while the platform is still being built
  ([10. Roadmap](../docs/10-roadmap.md)).
- Evidence that collects itself, for a team of two to four.
- Criteria that match what customers ask about, not the maximum.

## Options

| | Covers where customer data goes | Feasible | Evidence effort |
|---|---|---|---|
| Leave the platform out of the system description | ✘ | ✔ | none, until a customer asks |
| Include it, with the vendors' controls tested by the company's auditor (inclusive method) | ✔ | ✘ vendors do not allow it | very high |
| **Include it, vendors carved out: their own SOC 2 Type II reports, plus the complementary controls they require of their customers** | ✔ | ✔ | moderate, mostly automated |

| Trust Services Criteria | In scope | Why |
|---|---|---|
| Security (common criteria) | ✔ | required |
| Availability | ✔ | customers' usage pages read from the platform's path from stage 2; Q9 restores |
| Confidentiality | ✔ | customer data, classified, retained and disposed of by rule |
| Processing integrity | ✘ for now | revenue reporting is internal; revisit if billing is computed from platform data |
| Privacy | ✘ in SOC 2 | handled under the GDPR programme and the DPA; revisit if customers ask for it |

## Decision

The analytical platform is inside the company's SOC 2 system description from the day it
holds customer data, under Security, Availability and Confidentiality. AWS and the platform
vendor are carved out: their SOC 2 Type II reports are obtained and reviewed every year, and
the complementary user entity controls they list are mapped to the company's own controls. The
control matrix, the evidence each control produces and how it is collected are in
[12. SOC 2 readiness](../docs/12-soc2-readiness.md); platform objects are in Terraform, and
access evidence comes from the platform's own tags and lineage, not from a spreadsheet.

## Consequences

- The replica the BI tool reads in stage 0 is in scope from month three too: analysts get
  personal roles on it before the window opens ([10. Roadmap](../docs/10-roadmap.md)).
- Every platform change goes through a reviewed pull request (CC8.1); console changes are
  drift, found by `terraform plan` and reverted.
- Vendor report exceptions become the company's risks to assess, every year.
- Organisational controls (HR, training, the risk committee) are the company's, outside the
  platform; the platform supplies evidence for the technical ones.

## Revisit when

Billing is computed from platform data (add Processing Integrity), a customer contract asks
for the Privacy criterion, a vendor's report shows an exception, or the platform choice
changes.

## Evidence

<!-- evidence:start -->
- **5 of 5** columns tagged personal whose every read in 90 days one query found, by reader, column and time, from the catalog's tags and the platform's column lineage. Databricks SQL 2026.39 on Free Edition: information_schema.column_tags (class = personal) joined to system.access.column_lineage; readers pseudonymised in the result; answered in 4.7 s. Source: [data-platform-architecture/results/poc-databricks-governance.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks-governance.json)
- **6 of 7** kinds of governance object Terraform owned on Databricks, with a clean plan after applying; the seventh, the mask function, needs SQL. OpenTofu 1.13.1 and the Databricks provider 1.138.0 from an empty state: the governed tag (adopted with an import block), schema, table, column tags, the tag-matching mask policy and grants; nine resources; a row read back masked. Source: [data-platform-architecture/results/poc-databricks-terraform.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks-terraform.json)
<!-- evidence:end -->
