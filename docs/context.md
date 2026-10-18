# Context

## The business

A B2B subscription product. Companies sign up for an account, put their people on it, and pay monthly on one of four plans; their people use the product every day. It is the business that [data-stack-lab](https://github.com/technobasant/data-stack-lab) generates data for, so the data-level behaviour cited here was measured on the same shape of data.

## Who reads the data

| Consumer | Wants | Latency it can accept | Failure it cannot accept |
|---|---|---|---|
| Finance | revenue by plan, segment and month | next morning | revenue on the wrong plan, or missing |
| Product analysts | usage, funnels, retention, any join | minutes to a day | silently missing days |
| Customers, inside the product | their own usage and activity | under a minute | another customer's data; numbers that change after the fact |
| The product's own features | per-tenant reads and writes | milliseconds | lost writes |
| Models (churn, fraud, recommendations) | point-in-time features | training: a day; serving: milliseconds | features from the future |

## Workload tiers

Every figure in the cost model and every sizing statement assumes one of three tiers. They are assumptions about a plausible SaaS business at three stages, not measurements of one.

| | Small | Medium | Large |
|---|---:|---:|---:|
| Customer accounts | 1,000 | 10,000 | 100,000 |
| Product events per day | 2 million | 30 million | 300 million |
| Raw event size | 1 KB | 1 KB | 1 KB |
| Stored per event, columnar (≈7× compression) | 150 B | 150 B | 150 B |
| Event history kept | 13 months | 13 months | 13 months |
| Event storage at steady state | ≈0.12 TB | ≈1.8 TB | ≈18 TB |
| Compute per day, transformation and analyst queries (hours of a medium-sized engine) | 3 | 9 | 20 |
| Data scanned per day by the same work, on engines that bill per scan | 0.07 TB | 0.8 TB | 8 TB |

The [cost model](../cost/) reads these from [`cost/workloads.yml`](../cost/workloads.yml); change them there.

## Constraints

- A small platform team: three to five engineers who build and run it. Operating cost in people matters as much as the bill.
- Customer-facing numbers must be tenant-isolated and must not change after the fact without a reason.
- Personal data (names, e-mail addresses) stays out of anything analysts or models read directly.
- No single vendor is assumed: storage stays in open formats so engines can change.

## Out of scope

Real-time decisioning beyond feature serving; multi-region data residency; the product's own application architecture beyond its database.
