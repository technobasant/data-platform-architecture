# 0003. Files that land are immutable, and every load writes by key

- Status: Accepted
- Date: 2026-10-19
- Deciders: data lead, VP Product (for the event producers); proposed by the architect
- Evidence: dsl_databricks_corrected_missed, dsl_quality_block

## Context

Product events and the Stripe export reach the platform as files in S3. Real deliveries
are duplicated, cut short, late, corrected and re-sent. File-tracking loaders (`COPY INTO`,
Snowpipe, Auto Loader) are idempotent by path: a file is loaded once. That makes re-runs
safe and makes a correction under the same name invisible.

## Decision drivers

- Q6: re-runs and late files lose nothing and double nothing.
- Q7: a corrected file replaces what it corrects.
- Q5: yesterday complete by 06:00 UTC without a person checking.

## Options

| | Re-run safe | Late file | Duplicate file | Correction under the same name | Correction under a new name |
|---|---|---|---|---|---|
| Load each day's files by name | ✘ doubles | ✘ missed | ✘ doubles | ✘ missed | ✘ missed |
| File-tracking loader, append | ✔ | ✔ | ✘ doubles | ✘ never read | ✘ doubles |
| File-tracking loader re-reading changed files, append | ✔ | ✔ | ✘ doubles | ✘ old rows doubled | ✘ doubles |
| **Immutable files + file-tracking loader + `MERGE` on the record's key** | ✔ | ✔ | ✔ | n/a: forbidden by contract | ✔ |

All five outcomes were measured on Databricks, with a prediction from the documented
semantics that the run matched exactly.

## Decision

- Producers write each file once. A correction is a new file with a new name; the contract
  with each producer says so ([0013](0013-contracts-at-the-producer.md)).
- Files are loaded by a file-tracking loader into an append-only raw table, then merged
  into the cleaned table on the record's own key (`event_id`, the Stripe object id), so
  duplicates and corrections resolve there.
- Each file's row count is checked against the producer's manifest before the merge, so a
  truncated file stops the day instead of waiting for its correction.

## Consequences

- Duplicates cost nothing, and corrections work, provided producers keep the contract. A
  producer that cannot is loaded with the platform's re-read option (Auto Loader's
  `allowOverwrites`) and the same merge, at the cost of re-reading whole files.
- Raw tables keep every delivery, including duplicates, for audit; they are expired after
  the retention window ([0012](0012-erasure.md)).
- Two writes per row instead of one.

## Revisit when

A producer moves to streaming delivery (stage 2), where the record key and the stream's
transactions take over this role.

## Evidence

<!-- evidence:start -->
- **1,638** events never loaded by COPY INTO and Auto Loader after a truncated file was corrected under the same name. Databricks Free Edition (Databricks SQL 2026.39): ten days of event files (29,095 events) delivered into a Unity Catalog volume and loaded six ways after each delivery; the counts matched a prediction made from the documented semantics. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **0 of 3,198** bad rows promoted when any failing data-quality check held the day. September delivered daily with nine injected defects and checked in dbt (contract, row tests, batch tests against seven accepted days, manifest control totals); every delivered row labelled good or bad by its defect. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
