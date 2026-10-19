# 0013. Every source has a contract, checked in the producer's CI

- Status: Accepted
- Date: 2026-10-19
- Deciders: CTO, data lead; proposed by the architect
- Evidence: dpa_contract_breaking, registry_false_negatives, registry_false_alarms

## Context

The product team changes its schema weekly, and today a renamed column surfaces as a broken
dashboard. Once the platform reads the product's tables by CDC and its events as files,
every product change is a change to the platform's input, and the platform team is two
people who are not in the product's code reviews.

## Decision drivers

- Q8: a breaking change is stopped before it ships, in the producer's CI.
- Q7: files immutable, corrections under new names ([0003](0003-files-immutable-loads-by-key.md)).
- The product team's speed: no meeting for safe changes.

## Options

| | Stops a breaking change before it ships | Safe changes need no one | Covers files and CDC |
|---|---|---|---|
| Find out from failing models | ✘ | ✔ | ✔ |
| Schema checks in the platform's ingestion | ✘ after the fact | ✔ | ✔ |
| **A versioned contract per source (Open Data Contract Standard), checked against the previous version in the producer's CI** | ✔ | ✔ | ✔ |

## Decision

Each source (the product tables captured by CDC, the event files, the Stripe export) has a
contract in the [Open Data Contract Standard](https://bitol-io.github.io/open-data-contract-standard/):
schema, keys, classification, delivery rules (immutable files, a manifest per file) and an
owner. The producer's CI compares a change with the previous version; a breaking change
fails until the platform's owner approves it with a migration. The contracts are in
[`models/contracts/`](../models/contracts).

## Consequences

- A small file per source to maintain, owned by the producing team.
- Compatibility checks have false alarms (2 of 51 labelled changes in the registry lab),
  which cost an approval each; none of the breaking changes passed as safe.
- The contract's classification feeds masking ([0011](0011-tags-drive-masking-and-row-filters.md)).

## Revisit when

A producer cannot run a CI check (a vendor export); its contract is then checked at
ingestion instead, and a breach quarantines the file.

## Evidence

<!-- evidence:start -->
- **reported as breaking** what `datacontract breaking` says for the product contract with users.email renamed; an unchanged copy is not reported as breaking. The contracts CI job runs datacontract breaking original renamed, where renamed is the product contract with only users.email renamed to email_address (tests/fixtures/product-database-renamed-column.odcs.yaml); the job fails unless that command reports the change as breaking, and also fails unless datacontract breaking original original reports no breaking change. Source: [data-platform-architecture/.github/workflows/ci.yml](https://github.com/technobasant/data-platform-architecture/blob/main/.github/workflows/ci.yml)
- **0** breaking schema changes passed as safe, in any mode. 51 hand-labelled JSON Schema changes, each scored under BACKWARD, FORWARD and FULL; every label cross-checked by an oracle that ran 8,092 generated probe documents through a real JSON Schema validator. Source: [dataset-registry/MEASUREMENTS.md](https://github.com/technobasant/dataset-registry/blob/main/MEASUREMENTS.md)
- **2 of 51** changes flagged as breaking that are safe, per direction. The same 51 cases; a widened and a narrowed regular expression, an added anyOf branch and an added multipleOf are flagged in both directions by design, and each truly breaks only one. Source: [dataset-registry/MEASUREMENTS.md](https://github.com/technobasant/dataset-registry/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->
