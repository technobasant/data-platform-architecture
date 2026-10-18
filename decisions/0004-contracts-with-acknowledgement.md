# 0004. Contracts at every producer boundary; breaking changes wait for their consumers

- Status: Accepted
- Date: 2026-10-18
- Evidence: registry_false_negatives, registry_false_alarms

## Context

Most data incidents start with a change that looked harmless to its producer. Blocking every breaking change teaches teams to route around the check (a `_v2` table, a new topic). Allowing them silently means consumers find out from a broken report.

## Decision

- Every dataset and topic has an owning team and a versioned schema contract, checked in the producer's CI against the previous version.
- The checker may over-report but must never under-report: anything it cannot reason about counts as breaking.
- A breaking change is neither blocked nor shipped quietly. It becomes a change request that publishes only when every registered consumer has acknowledged it.

## Consequences

- On 51 labelled schema changes, the checker passed none of the breaking ones as safe, in any compatibility mode; it raised 2 false alarms per direction.
- Consumers must register to be protected, which needs ownership to be real, not a column in a spreadsheet.
- Changes that break consumers take as long as the slowest consumer to acknowledge. That is the intended cost.

## Alternatives considered

- **Schema registry compatibility alone.** Protects deserialisation, not meaning, and has no notion of who is affected.
- **No checks, versioned tables.** Every breaking change becomes a permanent new table.

## Evidence

<!-- evidence:start -->
- **0** breaking schema changes passed as safe, in any mode. 51 hand-labelled JSON Schema changes, each scored under BACKWARD, FORWARD and FULL; every label cross-checked by an oracle that ran 8,092 generated probe documents through a real JSON Schema validator. Source: [dataset-registry/MEASUREMENTS.md](https://github.com/technobasant/dataset-registry/blob/main/MEASUREMENTS.md)
- **2 of 51** changes flagged as breaking that are safe, per direction. The same 51 cases; a widened and a narrowed regular expression, an added anyOf branch and an added multipleOf are flagged in both directions by design, and each truly breaks only one. Source: [dataset-registry/MEASUREMENTS.md](https://github.com/technobasant/dataset-registry/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- dataset-registry [0003 Contracts are JSON Schema, checked on validity sets](https://github.com/technobasant/dataset-registry/blob/main/docs/adr/0003-json-schema-validity-sets.md), [0004 Breaking changes wait for consumer acknowledgement](https://github.com/technobasant/dataset-registry/blob/main/docs/adr/0004-acknowledgement-not-block.md)
- streaming-platform [0002 A transactional contract gate in front of Flink](https://github.com/technobasant/streaming-platform/blob/main/docs/adr/0002-transactional-contract-gate.md)
