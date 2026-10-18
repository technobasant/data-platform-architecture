# Governance

Governance here is the set of rules a pipeline cannot route around: who owns a dataset, what it may change, who may read it, and what happens to personal data.

## Ownership

Every dataset and topic has an owning team and a named person, recorded in a registry with its contract, its consumers and its freshness objective. A dataset first seen in lineage is recorded as unowned, and nobody can register as its consumer until a team claims it. ([dataset-registry](https://github.com/technobasant/dataset-registry))

## Contracts

- Every producer boundary has a versioned schema: Avro with FULL_TRANSITIVE compatibility for topics, JSON Schema for files and APIs, dbt contracts for marts.
- Changes are checked in the producer's CI against the previous version, in both directions: what breaks consumers reading new data, and what breaks history read with the new schema.
- A breaking change waits for every registered consumer to acknowledge it ([0004](../decisions/0004-contracts-with-acknowledgement.md)).

## Classification

| Class | Examples | Where it may appear |
|---|---|---|
| Public | plan names, prices | anywhere |
| Internal | usage counts, revenue | marts and serving stores, by role |
| Confidential | per-customer revenue, contract terms | marts, by named role only |
| Personal | names, e-mail addresses, IP addresses | `raw` and `staging` only; marts carry derived values (an e-mail domain, a hashed id) unless a use case is approved |

Classification is a column-level tag in the catalog and in the dbt model's YAML, so a contract change that adds a personal column fails review rather than shipping.

## Access

- Engines never hold storage keys. The Iceberg catalog vends short-lived credentials scoped to the table and the operation ([0002](../decisions/0002-open-tables-scoped-credentials.md)).
- People get roles, not grants on tables: analyst, finance, model training, platform. Roles map to zones and classes above.
- Service accounts are per job, so the audit log says which job read what.

## Personal data: retention and erasure

| Zone | Retention | On an erasure request |
|---|---|---|
| `raw` | 13 months, then expired | rows deleted by key; snapshots containing them expired within the rollback window |
| `staging` | rebuilt every run | disappears on the next run |
| `snapshots`, `marts` | indefinitely | personal columns are not there; derived keys are rotated if they could re-identify |
| Serving stores | by use case | deleted by key, verified by query |

Erasure is designed, not yet exercised. The proof it needs is a query across every zone, snapshot and serving copy that returns nothing for the erased person, run after the rollback window has passed.

## Lineage

Jobs emit OpenLineage run events, so the registry knows which datasets read which. Lineage is what turns "this schema change breaks someone" into a named list of consumers to ask.
