# ADR 0003 — Credit Cards conversion reward modelling

**Status:** Accepted — 2026-05-15
**Context tag:** Credit Cards MVP (Phase 1)
**Supersedes:** none

## Context

Credit Cards monetises a single click across several events that
happen over weeks, not seconds:

| Event | Typical lag from click | Client value |
|---|---|---|
| Application started | hours – days | small acquisition-cost recovery |
| Application submitted | hours – days | medium |
| Application approved | days – weeks | large |
| Card activated + first eligible spend | 30 – 60 days | full lifetime-value share |

Through `v0.1.9` the platform assumes one `realized_rpc` per click,
sourced from one row per `click_id` in `sales_ledger`. That fits the
synthetic seed and was sufficient for the demo, but it does not
represent how Credit Cards actually pays out.

Two viable approaches:

1. **Sum-of-rewards in a single regression target.** The label for
   training is `SUM(revenue)` over all ledger rows for that `click_id`
   inside the reconciliation window. One model learns expected total
   value.

2. **Separate sub-models per stage, combined at serving time.** Three
   probability models (started, approved, first-spend) × stage values,
   summed at serving time. Higher fidelity; requires more data and a
   serving-time orchestration layer that combines sub-model outputs.

## Decision

**Adopt Option 1 for the Credit Cards MVP.**

- `sales_ledger` ingestion writes one row per ledger event with the
  `revenue` field carrying that event's value (signed: a charge-back
  is negative).
- `predictions_vs_revenue` view already uses `SUM(revenue) GROUP BY
  click_id` — semantics intact; add a clarifying comment.
- Single XGBoost regressor; label is total in-window revenue.
- Revisit at the 80% coverage milestone (end of June) once we have
  enough labelled volume to fit three sub-models without overfitting.

## Consequences

**Positive**
- Reuses the existing model architecture, training pipeline, and
  serving path. No new services.
- Refunds, charge-backs, fee adjustments fold cleanly into the same
  label as signed ledger rows.
- A simple ablation against per-stage sub-models is straightforward
  once volume permits.

**Negative**
- Predicted RPC is a blended estimate. The model cannot tell us
  *why* a click is valuable (approval vs activation). For the MVP this
  is acceptable; SHAP attributions still surface the input features
  driving the price.
- Calibration becomes harder when the stage-value mix shifts (e.g. a
  campaign skewing toward applications-only): the residual chart will
  show systematic over- or under-prediction even if the per-stage
  model would be on point.

## Implementation notes

- `services/reconciliation/sql/predictions_vs_revenue.sql` already has
  `SUM(revenue) … GROUP BY click_id`. Add a comment recording this ADR
  and the semantics.
- No domain or adapter changes in `scoring-api`.
- Drift monitor: add a panel that tracks per-stage *volume mix* over
  time so an unexplained calibration error has a place to be diagnosed.

## Revisit trigger

- Coverage reaches 80% (end of June 2026), **and**
- We have ≥ 30k labelled clicks across all four stages with each
  stage represented ≥ 5%.
