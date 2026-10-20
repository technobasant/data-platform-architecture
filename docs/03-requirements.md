# 3. Requirements

What the platform has to do for each group in [the brief](01-brief.md), and the quality
targets it is held to. Each target is a scenario that can be tested: something happens,
the platform responds, and a number says whether the response was good enough.

## Who reads what

| Consumer | Needs | How fresh | What must never happen |
|---|---|---|---|
| Finance | revenue by plan, segment and month; MRR movements; reconciled to Stripe | yesterday, by 06:00 UTC | revenue under the wrong plan; a total that disagrees with billing |
| Product analysts | usage, funnels, retention, cohorts over all history; ad hoc SQL | yesterday | a day silently missing or counted twice |
| Customer success | account health: activity trends, seats used, plan changes | yesterday | a report that times out or is cancelled |
| Customers, in the product | their own usage page and an export of it | under a minute (stage 2) | another customer's rows; the product slowing down |
| The assistant (stage 3) | governed, documented tables to answer customers' questions from | as the usage page | anything the asking customer may not see |
| Security and compliance | access reviews, audit logs, erasure evidence | on demand | personal data where it is not allowed; an erasure that cannot be proven |

## Quality scenarios

"Today" is the current state, measured on the lab copy of the company's database where a
number is given ([2. Current state](02-current-state.md)). "Stage" is the stage of the
[target architecture](05-target-architecture.md) that meets it.

| # | Quality | Scenario | Target | Today | Verified by | Stage |
|---|---|---|---|---|---|---|
| Q1 | Product isolation | analysts run every BI report while the product serves its normal load | product p99 latency no more than 20% above its p99 with no reports running | p99 483 ms → 1,847 ms with reports on the primary | the baseline harness, re-run against the target | 1 |
| Q2 | Report reliability | an analyst runs any report while the product writes | completes on the first attempt, 99 runs in 100 | 3 of 35 long reports finished on the replica at the brief's peak rate | BI query log | 1 |
| Q3 | Correct attribution | finance reports revenue by plan for any past month | every invoice on the plan it billed; totals equal Stripe's to the cent | 15.1% of a year's revenue on the wrong plan | reconciliation test in the build | 1 |
| Q4 | History | an analyst asks about activity 20 months ago | the events are there | deleted after 90 days | row counts per month | 1 |
| Q5 | Batch freshness | finance opens the revenue dashboard | yesterday complete by 06:00 UTC, 29 days in 30 | nightly CSV, not checked | freshness check per table | 1 |
| Q6 | Re-runs and late data | a day is re-run, backfilled out of order, or a file arrives up to 10 days late | nothing lost, nothing counted twice | not tested | backfill tests in CI | 1 |
| Q7 | Corrections | a source re-sends a corrected file | the correction replaces what it corrects | not applicable | ingestion tests | 1 |
| Q8 | Change safety | a source changes its schema in a way that breaks a consumer | stopped before it ships, in the source's CI | breaks dashboards | contract checks | 1 |
| Q9 | Recovery | a bad write or delete to any analytical table is found up to 7 days later | the table is restored within 1 hour | not possible | quarterly restore drill | 1 |
| Q10 | Erasure | a person's erasure request is received | their data is gone from every table, copy and history within 30 days, and a query proves it | not possible | erasure drill | 1 |
| Q11 | Tenant isolation | a customer reads usage through any path open to them | only their own account's rows | enforced in application code only | adversarial tests per path | 2 |
| Q12 | Customer freshness | a customer does something in the product | it appears on their usage page within 60 s, p99 | read from the primary, current | freshness probes | 2 |
| Q13 | Access audit | the auditor asks who read personal or confidential data last quarter | answered from logs in under a day, per person and per job | shared database login | audit-log query | 1 |
| Q14 | Cost | the platform runs for a month | under $15,000 including the vendor bill; cost per account reported | the RDS replica and the BI tool | monthly bill by tag | 1 |
| Q15 | Operability | a pipeline fails at night | nothing customer-facing breaks; it is fixed in business hours | not applicable | runbooks, pager rules | 1 |

Q1 and Q2 are the targets the current state misses outright. Q3, Q4 and Q10 are the ones
the business has already been hurt by or committed to. Q11 and Q12 belong to the
customer-facing work in stage 2, and are why stage 2 exists.

## Ranking

When two targets pull against each other, they rank in this order: tenant isolation (Q11),
erasure (Q10), product isolation (Q1), correct numbers (Q3, Q6, Q7), then freshness and
cost. A late dashboard is a bad morning; another customer's data, or an erasure the
company cannot prove, is a contract breach.

---

[← 2. Current state](02-current-state.md) · [README](../README.md) · [4. Options →](04-options.md)
