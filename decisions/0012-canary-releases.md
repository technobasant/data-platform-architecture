# 0012. Platform services ship by canary, judged against the stable version

- Status: Accepted
- Date: 2026-10-18
- Evidence: deploy_bad_release_aborted, deploy_good_release_failures

## Context

The platform's own services (ingestion APIs, the registry, query gateways) change weekly. A bad release of an ingestion API loses data, not just requests.

## Decision

- Services deploy through GitOps, with a canary whose latency and error rate are compared with the stable version's, not with absolute thresholds.
- A canary is not promoted without a minimum number of requests observed: no evidence is not a pass.
- Admission policies reject manifests that break platform rules (latest tags, missing limits) before they run.

## Consequences

- Six of six bad releases were aborted by the analysis; across three good releases, 0 of 18,003 requests failed.
- Releases take minutes longer, and analysis needs real traffic to judge.

## Alternatives considered

- **Absolute thresholds.** The first version of the analysis aborted a good release and promoted a bad one.

## Evidence

<!-- evidence:start -->
- **6 of 6** bad releases aborted by canary analysis. A release whose Envoy sidecar returns 500 on 30% of requests, under 20 req/s from k6; three runs with keep-alive clients, three with a new connection per request; Prometheus analysis every 15 s after a 30 s initial delay. Source: [platform-deployments/MEASUREMENTS.md](https://github.com/technobasant/platform-deployments/blob/main/MEASUREMENTS.md)
- **0 of 18,003** requests failed across three good canary releases. K6 at 20 req/s for five minutes per run, GET /healthz and GET /review-queue with a 10 s timeout; canary 20% → 50% with 60 s pauses, background analysis and an evidence step before 100%. Source: [platform-deployments/MEASUREMENTS.md](https://github.com/technobasant/platform-deployments/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- platform-deployments [0002 Argo Rollouts canary with Prometheus analysis](https://github.com/technobasant/platform-deployments/blob/main/docs/adr/0002-rollouts-canary-with-analysis.md), [0005 Kyverno in Enforce mode](https://github.com/technobasant/platform-deployments/blob/main/docs/adr/0005-kyverno.md)
