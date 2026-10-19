# 0016. Kimball marts over a raw change history, without a Data Vault layer

- Status: Accepted
- Date: 2026-10-20
- Deciders: data lead, CFO (for revenue reporting); proposed by the architect
- Evidence: dsl_type2_correct, dsl_type1_misattributed, dsl_dbt_databricks, dpa_erasure_model

## Context

The platform has two sources today, the product's database by change data capture
([0002](0002-cdc-from-the-product-database.md)) and Stripe's daily files
([0003](0003-files-immutable-loads-by-key.md)), and a data team of two growing to four. Its
readers are the BI tool and, in stage 3, the assistant; both read tables, not models. Revenue
must be read against the plan in force at the time (Q3), history must reach back 25 months
(Q4), every change must be auditable, and a person must be erasable everywhere (Q10).

The layers between a source and a dashboard are a modelling decision with a long tail: they
decide how much there is to build, test and erase for every new column.

## Decision drivers

- Q3: every invoice on the plan it billed, for any past month.
- Q4 and Q13: history and an audit trail of every change at the source.
- Q10: as few places holding personal data as possible ([0017](0017-personal-data-in-one-place.md)).
- A team of two to four, with dbt, and one model to keep consistent.
- The BI tool and the assistant read stars; neither can join a vault.

## Options

| | History as of any date (Q3) | Every source change kept | Tables to build per source entity | Readable by the BI tool as built | Where personal data ends up |
|---|---|---|---|---|---|
| One wide table per subject | ◐ needs snapshots | ✘ | 1 | ✔ | in every wide table: erasing one person rewrote all 31.85 million event rows |
| Inmon: a normalised warehouse, then marts | ✔ | ◐ | 2 models | ✘ through marts | in the warehouse and the marts |
| Data Vault 2.0: hubs, links and satellites, then marts | ✔ | ✔ | 3 or more, plus point-in-time and bridge tables to query | ✘ through marts | in satellites, which can isolate it well |
| **A raw change log, staging, Type 2 history, Kimball marts** | ✔ built from the change rows | ✔ the raw log keeps every change with its log position | 2: staging and the mart | ✔ | raw, staging and one user table only ([0017](0017-personal-data-in-one-place.md)) |

## Decision

Sources land unchanged in `raw`: the CDC change log, with every insert, update and delete
and its log position, and the Stripe files. `staging` types and de-duplicates them into
current state. Type 2 history for the attributes facts are reported by is built from the
change rows ([0007](0007-history-for-attributes-facts-read-against.md)), and the marts are a
Kimball star with conformed dimensions, described in [6. Data model](../docs/06-data-model.md).

Data Vault's strengths are auditability, integrating many sources whose business keys
overlap, and loading them in parallel. Here the raw change log already gives the audit trail
and a full rebuild, and two sources do not overlap: a vault would triple the tables to build
and test and add a point-in-time layer before anyone could query them, for no requirement it
alone meets.

## Consequences

- Any mart can be rebuilt from `raw` at any time; history is not lost in a model change.
- A new source adds a staging model and, if it shares an entity, conforms to the existing
  dimension (one `dim_account` whichever source mentions the account).
- Integrating sources with conflicting keys for the same entity is harder without hubs: it is
  a mapping table and a decision per entity, done in staging.
- The model is portable: the same dbt project built on DuckDB and on Databricks with one
  change to contract types.

## Revisit when

More than about eight sources describe overlapping entities (an acquisition brings a second
product database, a CRM becomes a source of truth for accounts), or an auditor requires
record-level lineage from a mart row to every source record beyond what the raw log gives.

## Evidence

<!-- evidence:start -->
- **5,048 of 5,048** invoices on the plan they billed, Type 2 dimension from dbt snapshots. As-of join of each invoice to the dim_account version in effect at billing, scored against the generator's truth file; the dimension was built from 13 monthly snapshot loads. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **15.1%** of a year's revenue on the wrong plan with a Type 1 account dimension. 5,048 synthetic invoices (seed 7, Oct 2025 – Sep 2026) attributed by each account's current plan and compared with the plan the generator billed; $152,227 of $1,010,202. Source: [data-stack-lab/MEASUREMENTS.md](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)
- **11, 46, 3** models, data tests and unit tests that passed when the dbt project was built on Databricks after one change, with revenue figures identical to DuckDB's. Dbt-databricks 1.12.7 on Databricks SQL 2026.39: the 13 monthly extracts replayed through dbt snapshot, then dbt build; measure.py's revenue questions asked of the Databricks marts with the same SQL. The one change: contract types varchar became string, because Databricks refuses VARCHAR without a length. Source: [data-stack-lab/results/dbt-databricks.json](https://github.com/technobasant/data-stack-lab/blob/main/results/dbt-databricks.json)
- **31,849,449 rows** rewritten to erase one person (551 events) when the model copies e-mail and name into every event row; 59,999 when they live only in a 60,000-row user table. Databricks SQL 2026.39 on Free Edition, UniForm tables (no deletion vectors) built from the proof of concept's 31.85 million events: UPDATE … SET email = NULL, full_name = NULL for one user; the wide table's 3 files were all rewritten (7.6 s), the user table's 1 file (1.1 s); on plain Delta with deletion vectors the update wrote 3 vectors and the purge then rewrote all 3 files. Source: [data-platform-architecture/results/poc-databricks-governance.json](https://github.com/technobasant/data-platform-architecture/blob/main/results/poc-databricks-governance.json)
<!-- evidence:end -->
