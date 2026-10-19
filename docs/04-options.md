# 4. Options

Five ways to meet the [requirements](03-requirements.md), compared against them, the
[constraints](01-brief.md#constraints) and the cost model. The client asked for a choice
between Databricks and Snowflake; the other three are here because a recommendation is only
as good as what it was compared with, and because one of them is the right answer for the
first three months.

## The options

| | Option | In one line |
|---|---|---|
| A | **Scale the Postgres setup** | a dedicated reporting replica, partitioned events, summary tables, longer retention |
| B | **AWS-native, lean** | Iceberg tables on S3, the Glue catalog, Athena, Lake Formation; AWS DMS for change data capture |
| C | **Databricks** | Delta tables on the client's S3, Unity Catalog, serverless SQL and Lakeflow pipelines |
| D | **Snowflake** | Snowflake-managed tables (or Iceberg tables on S3), Enterprise edition, Openflow or Snowpipe for ingestion |
| E | **Self-run open lakehouse** | Iceberg, a REST catalog, Trino and Airflow on Kubernetes |

## Against the requirements

✔ meets it; ◐ meets it with work the option does not do for you; ✘ does not meet it.

| Requirement | A Postgres | B AWS-native | C Databricks | D Snowflake | E Self-run |
|---|---|---|---|---|---|
| Q1 product isolation | ◐ only if BI never touches the primary | ✔ | ✔ | ✔ | ✔ |
| Q2 reports finish first time | ✘ the replica cancels them, or holds back the primary's vacuum ([measured](02-current-state.md)) | ✔ | ✔ | ✔ | ✔ |
| Q3 correct attribution | ◐ history has to be built in Postgres | ✔ with dbt | ✔ with dbt | ✔ with dbt | ✔ with dbt |
| Q4 25 months of history | ✘ 760 million to 3.8 billion rows in a row store | ✔ | ✔ | ✔ | ✔ |
| Q6, Q7 re-runs, late and corrected files | ◐ | ◐ assembled from Glue jobs and `MERGE` | ✔ Auto Loader and `MERGE`, with [care over corrected files](https://basantbhattarai.com.np/writing/copy-into-never-read-the-corrected-file/) | ✔ Snowpipe and `MERGE` | ◐ |
| Change data capture from RDS Postgres | not needed | DMS, platform-neutral | Lakeflow Connect, **Public Preview** and by enrolment; or DMS | Openflow connector, **generally available** (gen 1) | Debezium and Kafka, self-run |
| Q9 restore a table | ✘ beyond whole-database restore | ✔ Iceberg snapshots | ✔ Delta `RESTORE` ([measured](https://github.com/technobasant/data-stack-lab/blob/main/MEASUREMENTS.md)) | ✔ Time Travel, up to 90 days on Enterprise | ✔ Iceberg snapshots ([measured](https://github.com/technobasant/lakehouse-lab)) |
| Q10 erasure, provably | ✔ one database | ◐ delete, then expire snapshots | ◐ delete, then `VACUUM` past the retention window | ◐ delete; Time Travel, then 7 days of Fail-safe on permanent tables | ◐ as B |
| Q11, Q13 tenant isolation, masking, audit | ◐ application code; one shared login | ◐ Lake Formation filters; CloudTrail | ✔ Unity Catalog row filters, column masks, audit logs | ✔ row access and masking policies (Enterprise), access history | ✘ to be built |
| Q12 usage in the product under 60 s | ✔ today, by loading the primary | ◐ needs a serving store (stage 2) | ◐ needs a serving store (stage 2) | ◐ needs a serving store (stage 2) | ◐ as C |
| Stage 3: the assistant | ✘ | ◐ Bedrock, built | ◐ the customer-facing assistant is the client's own service regardless of platform ([ai-platform-architecture 0004](https://github.com/technobasant/ai-platform-architecture/blob/main/decisions/0004-own-service-genie-for-staff.md)); AI/BI Genie on governed tables is for staff only | ◐ same: the client's own service for customers; Cortex Analyst on governed tables is for staff only | ✘ built |
| Runs with a team of two to four | ✔ | ◐ many services to wire | ✔ serverless | ✔ | ✘ about one engineer full time |
| Leaving it later | n/a | ✔ open tables in the client's account | ◐ Delta on the client's S3, readable as Iceberg through UniForm | ◐ Snowflake tables need export; Iceberg tables do not | ✔ |

## Cost

The vendor bill for the analytical layer at the client's scale, from list prices, and the
same with the share of an engineer each option is assumed to take. Both rest on assumptions
stated in [`cost/workloads.yml`](../cost/workloads.yml); the platform PoC replaces the
compute assumption with measured usage. Ingestion services (DMS, Openflow, Lakeflow
Connect) and the stage-2 serving store are not in these figures.

<!-- cost:start -->
List prices in AWS EU (Ireland), eu-west-1, retrieved 2026-10-19 ([`cost/prices.yml`](../cost/prices.yml)).

**Break-even.** One hour of a medium-sized engine costs the same as scanning this much on a per-scan engine. Below it, per-scan is cheaper; above it, paying for the hour is.

| Engine paid by the hour | USD per hour | TB scanned on Athena for the same money |
|---|---:|---:|
| Snowflake Enterprise | $15.60 | 3.12 TB |
| Snowflake Business Critical | $20.80 | 4.16 TB |
| Databricks SQL Serverless | $21.84 | 4.37 TB |
| Trino on EC2 (workers only) | $2.37 | 0.47 TB |

**The client's scale**, today and in its growth plan, under the assumptions in [`cost/workloads.yml`](../cost/workloads.yml). The vendor bill for the analytical layer, per month:

| Option | Today | In 12 months | In 36 months |
|---|---:|---:|---:|
| Snowflake Enterprise | $713 | $1,426 | $2,862 |
| Snowflake Business Critical | $950 | $1,900 | $3,811 |
| Databricks SQL Serverless | $997 | $1,995 | $4,001 |
| Trino on EC2 | $437 | $547 | $777 |
| Athena | $3 | $11 | $55 |
| *assumed TB scanned per engine-hour* | 0.007 | 0.017 | 0.042 |
| *stored TB* | 0.052 | 0.148 | 0.741 |

**With the people to run it**: the bill plus the share of an engineer each option is assumed to take, per month:

| Option | Today | In 12 months | In 36 months |
|---|---:|---:|---:|
| Snowflake Enterprise | $1,813 | $2,526 | $3,962 |
| Snowflake Business Critical | $2,050 | $3,000 | $4,911 |
| Databricks SQL Serverless | $2,647 | $3,645 | $5,651 |
| Trino on EC2 | $11,437 | $11,547 | $11,777 |
| Athena | $2,753 | $2,761 | $2,805 |
<!-- cost:end -->

Prices are for AWS EU (Ireland), the client's region. Snowflake Standard is not shown: it
cannot meet the requirements (masking and row access policies, and Time Travel past one day,
need Enterprise). Business Critical is shown because PrivateLink to Snowflake needs it; on
Databricks, PrivateLink is on the Enterprise tier at the same price per DBU. BigQuery is not
an option: it is a Google Cloud service, and
[0006](../decisions/0006-open-format-in-the-clients-account.md) keeps the client's data in
storage the client owns, in its own AWS account.

At this scale **the bill does not decide it**. Every managed option stays far inside the
$15,000 a month budget at 36 months, and per-scan engines (Athena) cost almost nothing. The
self-run lakehouse is the second-cheapest bill and by far the most expensive option once
the engineer it needs is counted. What separates the managed options is what they do for a
team of two to four, and what they cost when usage turns out higher than assumed: the
break-even table above says when paying per hour beats paying per scan.

## Recommendation

1. **Now: option A as a stopgap, for three months at most.** Point every BI query at the
   replica, never the primary, and make the replica the reports' alone with a 15-minute
   replay delay ([0001](../decisions/0001-analytics-off-the-product-database.md)): in the
   lab every report then finished, and the replica fell minutes behind, which no report
   minds. It costs nothing and protects the product while the platform is built. It cannot
   meet Q4, and it is not the destination.
2. **Destination: C or D, decided by a two-week proof of concept** on criteria fixed before
   it starts ([0005](../decisions/0005-databricks-or-snowflake.md)). Both meet the stage-1
   requirements on paper. The differences that matter for this client can be measured: the
   bill for its actual workload, ingestion from RDS with re-sent and late files, masking and
   row filters per tenant, erasure through time travel, and the effort to run each.
3. **B is the control.** It is the cheapest credible option and stays on the table if the
   PoC shows that neither platform's features are worth their bill. Its cost is assembly:
   catalog, ingestion jobs, table maintenance and access policies wired together by a team
   of two.
4. **E is rejected for year one.** It breaks the managed-first constraint and needs about
   an engineer full time; keeping tables in open formats (C with UniForm, D with Iceberg
   tables, or B) keeps it possible later.

The decision records: [0001](../decisions/0001-analytics-off-the-product-database.md)
(analytics leaves the product database), [0004](../decisions/0004-managed-platform.md)
(managed, not self-run), [0005](../decisions/0005-databricks-or-snowflake.md) (Databricks
or Snowflake, Proposed until the PoC).

---

[← 3. Requirements](03-requirements.md) · [README](../README.md) · [5. Target architecture →](05-target-architecture.md)
