# Quality attributes

Each target is a design commitment for the reference platform. The evidence column says what the labs have measured toward it, and the last section says what has not been measured at all.

| Attribute | Target | Why this target | How it is measured | Evidence so far |
|---|---|---|---|---|
| Freshness, real-time | p99 from event to queryable under 60 s | customers look at their own usage inside the product; a minute is the longest a screen can lag a click without support tickets | probe events written at the source, timed until queryable in the serving store | 6.1 s p99 at 1,000 events/s |
| Detection of a stalled stream | page within 5 min | the real-time objective's error budget is small | multi-window burn-rate alert on the freshness probes | 59–62 s from a frozen pipeline to a page |
| Freshness, batch | daily marts complete by 06:00 UTC | finance and analysts start their day on yesterday | last successful write per dataset, checked on an interval | a breach is noticed half an interval late at the median: 7.5 s at 15 s |
| Completeness | every delivered event counted exactly once in every record layer | an undercount looks like churn; an overcount looks like growth | per-layer counts reconciled to the topic after every run and failure | 9 of 9 failure runs exact |
| Completeness under re-runs and backfills | no day lost or doubled, in any run order | backfills and re-runs are routine, not incidents | backfills in order, late, and newest-first, scored against what arrived | 0 lost by the interval model in all orders; 96.56% lost by watermarks newest-first |
| Correctness | facts attributed to the attribute version in effect when they happened | plan-level revenue drives pricing and compensation | unit tests on as-of joins; labs scored against known answers | 5,048 of 5,048 invoices; Type 1 would misplace 15.1% |
| Change safety | no breaking schema change ships without its consumers' acknowledgement | the most common incident is a harmless-looking change | contract check in the producer's CI | no breaking change passed as safe, across 51 labelled changes |
| Recoverability, Postgres | RPO under 1 min, RTO under 5 min | product writes are the one thing that cannot be replayed from elsewhere | failover and point-in-time restore drills | promotion in 10–20 s; replica rebuilt in about 5 s; a dropped table's 5 of 5 rows restored |
| Recoverability, tables | any table restorable to any point in the last 7 days | a bad write is usually noticed within days, not hours | snapshot rollback drill | 909,968 rows restored by rollback |
| Release safety | a bad release of a platform service is stopped before it reaches every pod | ingestion APIs lose data, not just requests, when they fail | canary analysis against stable | 6 of 6 bad releases aborted; 0 of 18,003 requests failed on good ones |
| Isolation | no customer sees another customer's data | contractual and regulatory | tenant key first in every serving sort key and distribution key; tests per query path | not measured as a test suite yet |

## Not measured yet

- **Cost.** Modelled from list prices in [../cost/](../cost) for three workload tiers; no platform bill has been observed.
- **CDC under failover.** Designed in [0001](../decisions/0001-three-ways-in.md); replication-slot behaviour across a Postgres promotion is the measurement still owed.
- **Erasure.** Deleting one person's data from every zone, every snapshot and every serving copy, and proving it, is designed in [governance](governance.md) and not yet exercised.
- **Isolation.** Asserted by design (tenant-first keys); no adversarial test suite yet.
- **Capacity.** The labs run multi-node clusters on one host; they show behaviour, not throughput at the Large tier.
