# 0012. Erasure: delete by key, then let every copy of the old version expire inside 30 days

- Status: Proposed
- Date: 2026-10-19
- Deciders: security and compliance lead, CTO; proposed by the architect
- Evidence: dpa_erasure_time_travel, dpa_erasure_after_retention, dpa_erasure_uniform

## Context

The data processing agreement commits to erasing a person's data within 30 days of a
request, everywhere it is held. A table format that can be restored to last week
([0015](0015-restore-points.md)) also still holds last week's rows: a delete is not an
erasure until every earlier version that contains the row is gone. On Snowflake, permanent
tables add 7 days of Fail-safe after Time Travel, which no customer can shorten.

## Decision drivers

- Q10: erased within 30 days, and provably.
- Q9: tables restorable for 7 days.
- Raw layers keep every delivery for audit ([0003](0003-files-immutable-loads-by-key.md)).

## Options

| | Inside 30 days | Restore still possible for 7 days | Provable |
|---|---|---|---|
| Delete rows, keep default retention | ◐ depends on the platform's defaults | ✔ | ✘ old versions not checked |
| Keep no history (no time travel) | ✔ | ✘ | ✔ |
| Pseudonymise at ingestion, erase the key map only | ✔ | ✔ | ◐ only if no direct identifier is ever stored |
| **Delete by person and account key in every layer, keep history windows short enough that old versions expire inside 30 days, then prove it** | ✔ | ✔ | ✔ |

## Decision

Proposed until the proof of concept has measured the timeline on both platforms (criterion 4
of [0005](0005-databricks-or-snowflake.md)); the Databricks half is measured
([11. Proof of concept](../docs/11-proof-of-concept.md#erasure-through-time-travel)):

- Personal data is kept to staging and named marts, with identifiers in a small set of
  tables keyed by `user_id`.
- An erasure deletes by key in every layer, including raw, within 7 days of the request.
- Every table's history window (Delta's deleted-file retention and `VACUUM`; Snowflake's
  Time Travel plus Fail-safe) is set so that a version containing a deleted row is
  unrecoverable by day 30.
- A proof query, run after day 30, searches every table and every reachable version for the
  person's identifiers and records the result.

## Consequences

- Restores are limited to the history window: 7 days is the floor set by Q9, and the
  ceiling is what erasure leaves.
- On Databricks, a `DELETE` alone erases nothing: with deletion vectors it rewrites no file,
  and every earlier version returns the rows. The weekly erasure job deletes and runs
  `REORG … APPLY (PURGE)`; `VACUUM` runs daily, on its own schedule, and once the table's
  retention has passed it removes the files a purge left behind, after which time travel to
  the earlier versions is refused. At the default 7-day retention, a request is
  unrecoverable within 15 days at the most: 7 days to the weekly job, 7 days of retention,
  and at most 1 day more for the daily `VACUUM` to run.
- On the format chosen in [0006](0006-open-format-in-the-clients-account.md), Delta with
  UniForm, deletion vectors are refused, so the `DELETE` itself rewrites the files and no
  purge is needed; time travel still returned every deleted row until the retention passed
  and `VACUUM` ran. The same 15 days hold, with one step fewer.
- Transient or managed-retention table types may be needed for raw layers on Snowflake to
  avoid Fail-safe; the Snowflake half of the proof of concept decides.
- Backups outside the platform (exports, the old S3 dumps of deleted events) are in scope,
  and the old dumps are deleted when the platform holds the history.

## Revisit when

The proof of concept completes; then Accepted with the measured timeline as evidence.

## Evidence

<!-- evidence:start -->
- **100 of 100** rows of an erased user still returned by time travel after DELETE and after REORG … APPLY (PURGE). Databricks SQL 2026.39 on Free Edition: a Delta table with deletion vectors; DELETE wrote 8 deletion vectors and rewrote 0 files; REORG APPLY (PURGE) rewrote 8 files; VERSION AS OF the version before the delete still returned every row, also after VACUUM at the default 7-day retention. Source: [data-platform-architecture/results/poc-databricks.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks.json)
- **refused** time travel to the version before the delete, once the table's deleted-file retention had passed and VACUUM had run. The table's delta.deletedFileRetentionDuration set to 1 hour for the test, VACUUM run after it passed; Databricks answered DELTA_UNSUPPORTED_TIME_TRAVEL_BEYOND_DELETED_FILE_RETENTION_DURATION. VACUUM RETAIN 0 HOURS was refused (DELTA_VACUUM_RETENTION_PERIOD_TOO_SHORT). Source: [data-platform-architecture/results/poc-databricks.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks.json)
- **8 files** rewritten by deleting one user's rows from a UniForm table, which refuses deletion vectors; time travel still returned all 100 rows until the retention passed. Databricks SQL 2026.39 on Free Edition: a Delta table with delta.enableIcebergCompatV2 and Iceberg as a universal format; creating it with deletion vectors failed with DELTA_ICEBERG_COMPAT_VIOLATION.DELETION_VECTORS_SHOULD_BE_DISABLED; DELETE removed 8 files and added 1; time travel refused only after a 1-hour retention and VACUUM. Source: [data-platform-architecture/results/poc-databricks.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks.json)
<!-- evidence:end -->
