# Choosing the analytical engine

Snowflake, Databricks, BigQuery, or an open lakehouse queried by Trino or Athena. All of them can serve this platform's analytical layer. They differ in how they charge, what they make easy, and what they ask of the team. Because the system of record is open Iceberg tables ([0002](../decisions/0002-open-tables-scoped-credentials.md)), the choice can be made per workload and changed later ([0013](../decisions/0013-managed-platform-per-workload.md)).

**Status.** The open-table design is measured in the labs. The managed platforms are compared here from list prices and documentation only; none has been run against this workload yet.

## Where each fits

| | Snowflake | Databricks | BigQuery | Open lakehouse (Trino or Athena on Iceberg) |
|---|---|---|---|---|
| Charges for | warehouse time, per second after a 60 s minimum | DBUs per hour of compute (serverless SQL includes the instances) | bytes scanned (on-demand) or slot-hours (editions) | instances you run (Trino) or bytes scanned (Athena), plus storage |
| Makes easy | SQL analytics with little to operate; data sharing; per-team warehouses | Spark, streaming and ML next to SQL; notebooks; Unity Catalog | serverless SQL at any size; nothing to size or suspend | engine choice; no per-query vendor bill; data stays in your account |
| Asks of the team | warehouse sizing and auto-suspend discipline | cluster and job configuration, unless everything is serverless | partitioning and clustering discipline, or costs follow the worst query | running and upgrading the engine, the catalog and table maintenance |
| Reads open Iceberg tables | yes (external and managed Iceberg tables) | through Unity Catalog's Iceberg support or UniForm | yes (BigLake Iceberg tables) | natively |
| Fits best when | SQL-first teams want least operations | the same team does data engineering, streaming and ML | usage is bursty and queries are well partitioned | the team can operate it, and lock-in or unit cost matters most |

## What decides it

1. **How much one hour of compute actually scans in your workload.** This decides between paying per scan and paying per hour more than anything else does (below). Query history gives both numbers: bytes scanned and warehouse time.
2. **Who will operate it.** A self-run lakehouse is the cheapest line on a bill and the most expensive in engineering time. The cost model does not price people; a team of three should count that first.
3. **What else runs next to SQL.** Streaming and ML on the same platform favour Databricks; SQL-only analytics favour Snowflake or BigQuery.
4. **Governance.** Column-level classification, masking and row filters exist on all three managed platforms and need building on an open lakehouse ([governance](governance.md)).
5. **Where the data has to stay.** Open tables in your own account keep that decision yours.

## What it would cost

<!-- cost:start -->
List prices retrieved 2026-10-18 ([`cost/prices.yml`](../cost/prices.yml)).

**Break-even.** One hour of a medium-sized engine costs the same as scanning this much on a per-scan engine. Below it, per-scan is cheaper; above it, paying for the hour is.

| Engine paid by the hour | USD per hour | BigQuery on-demand | Athena |
|---|---:|---:|---:|
| Snowflake Standard | $8.00 | 1.41 TB | 1.6 TB |
| Snowflake Enterprise | $12.00 | 2.11 TB | 2.4 TB |
| Databricks SQL Serverless | $16.80 | 2.96 TB | 3.36 TB |
| Trino on EC2 (workers only) | $2.12 | 0.37 TB | 0.42 TB |

**The three tiers**, under the assumptions in [`cost/workloads.yml`](../cost/workloads.yml):

| Option | Small | Medium | Large |
|---|---:|---:|---:|
| Snowflake Standard | $733 | $2,242 | $5,395 |
| Snowflake Enterprise | $1,098 | $3,336 | $7,827 |
| Databricks SQL Serverless | $1,536 | $4,650 | $10,746 |
| Trino on EC2 | $491 | $926 | $2,113 |
| BigQuery on-demand | $12 | $218 | $2,237 |
| Athena | $14 | $175 | $1,747 |
| *assumed TB scanned per engine-hour* | 0.023 | 0.089 | 0.4 |
| *stored TB* | 0.154 | 2.311 | 23.108 |
<!-- cost:end -->

### Reading the numbers

- **The break-even table is the robust result.** It depends only on list prices. If a typical hour of your medium-sized warehouse scans less than about 1.4–3 TB, per-scan pricing is cheaper; above that, paying for the hour is.
- **The tier totals depend on one assumption** that nothing here measured: how much data an hour of compute scans. Under the defaults, an hour scans well under a terabyte, so per-scan engines come out far cheaper at every tier. A workload of heavy full scans would reverse that.
- **Per-scan pricing punishes the worst query.** At the large tier, one query that ignores partitioning and reads the whole event history, about 18 TB, costs about $101 on BigQuery on-demand, every time it runs. Time-billed warehouses cap that cost and charge for idle time instead.
- **Trino on EC2 is cheap only on the bill.** The line covers four workers for the active hours and one always-on coordinator. It leaves out the catalog service, table maintenance, upgrades and the engineers who do them.

### Not modelled

BigQuery editions (slot-hours), Snowflake Gen2 and Interactive warehouses, Redshift Serverless, capacity commitments and discounts, data egress, catalog and orchestration services, and people. The prices are on-demand list prices in us-east-1 (BigQuery: US multi-region); re-check them in [`cost/prices.yml`](../cost/prices.yml) before using any figure.

## Using it for a real workload

1. Pull a month of query history from the current system: total bytes scanned and total warehouse (or cluster) hours.
2. Divide one by the other to get TB scanned per engine-hour, and compare it with the break-even table.
3. Put your own volumes into [`cost/workloads.yml`](../cost/workloads.yml) and run `python cost/model.py`.
4. Run the shortlist on a week of real queries before committing. The lab results in this repository came from running things, not from pricing pages; a platform choice deserves the same.
