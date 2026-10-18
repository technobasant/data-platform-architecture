# 0011. Features for models are served point-in-time correct, from one definition online and offline

- Status: Accepted
- Date: 2026-10-18
- Evidence: rtml_leakage, rtml_parity

## Context

A model trained on features joined without regard to time learns from the future. It validates well and fails in production. A feature computed one way for training and another way for serving drifts silently.

## Decision

- Training sets are built with point-in-time joins: each label sees only feature values that existed at its timestamp.
- Every feature is defined once and materialised to an offline store (lakehouse) and an online store; a parity test compares what training saw with what serving returns.
- Labels are used only once they are mature (for example, chargebacks that can arrive weeks later).

## Consequences

- A naive join validated at an AUC-PR of 0.746 and scored 0.363 on the next two weeks; the point-in-time join scored 0.941.
- 99.905% of 9,500 live requests were served exactly the features training used.
- A feature store is one more system; its value is the parity, not the storage.

## Alternatives considered

- **Compute features in the model service.** Fast to start; training and serving diverge.

## Evidence

<!-- evidence:start -->
- **0.363 vs 0.941** future AUC-PR, naive join against point-in-time join. Same rows, labels, model and hyperparameters; only the training join differs. Scored on the two weeks after training with point-in-time features and true labels, on seeded synthetic payments (874,446 transactions, 0.80% fraud). Source: [realtime-ml/MEASUREMENTS.md](https://github.com/technobasant/realtime-ml/blob/main/MEASUREMENTS.md)
- **99.905%** of 9,500 live requests served exactly the training features. Features logged by the API compared with Feast's point-in-time join for the same transactions, on a live stack replaying a day in about seven minutes. Source: [realtime-ml/MEASUREMENTS.md](https://github.com/technobasant/realtime-ml/blob/main/MEASUREMENTS.md)
<!-- evidence:end -->

## Related decisions in the labs

- realtime-ml [0002 Every window feature implemented twice, held together by a parity test](https://github.com/technobasant/realtime-ml/blob/main/docs/adr/0002-two-implementations-of-each-feature.md), [0003 Window semantics](https://github.com/technobasant/realtime-ml/blob/main/docs/adr/0003-window-semantics.md), [0004 Label maturity](https://github.com/technobasant/realtime-ml/blob/main/docs/adr/0004-label-maturity.md)
