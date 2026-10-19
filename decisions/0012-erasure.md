# 0012. Erasure: delete by key, then let every copy of the old version expire inside 30 days

- Status: Proposed
- Date: 2026-10-19
- Deciders: security and compliance lead, CTO; proposed by the architect
- Evidence:

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

Proposed until the proof of concept measures the timeline on both platforms (criterion 4 of
[0005](0005-databricks-or-snowflake.md)):

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
- Transient or managed-retention table types may be needed for raw layers on Snowflake to
  avoid Fail-safe; the proof of concept decides.
- Backups outside the platform (exports, the old S3 dumps of deleted events) are in scope,
  and the old dumps are deleted when the platform holds the history.

## Revisit when

The proof of concept completes; then Accepted with the measured timeline as evidence.

## Evidence

<!-- evidence:start -->
Not measured yet; see the status above.
<!-- evidence:end -->
