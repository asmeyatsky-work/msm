# PRD V2 — Strategy Alignment: From Predictive RPC to Value-Based Intelligence

**Status:** Draft for review — **S4 (Phoebe) pulled into the CC MVP 2026-05-18.** Phases below renumbered; see `docs/PRD-v2-credit-cards.md` §2.1 item 8 and §13 for the new schedule.
**Author:** Allan Smeyatsky
**Date:** 2026-05-18 (re-plan 2026-05-18)
**Companion to:** `docs/PRD-v2-credit-cards.md` (single-vertical hardening)
**Scope:** Platform-level changes required to satisfy the MSM "Smart Bidding → Predictive RPC → Value-Based Intelligence" strategy.

---

## 1. Why this document exists

`docs/PRD-v2-credit-cards.md` covers what is needed to ship the existing
Predictive RPC Estimator against one vertical (Credit Cards) for the first
real client engagement. It does **not** cover the broader strategy the MSM
Ads team wrote down — Cerberus (fraud), Phoebe (intent), Soteria (profit),
CRM/LTV, dynamic creative, MMM halo, and multi-vertical roll-out.

This PRD enumerates the gap between **what the strategy promises** and
**what the platform actually does today**, and proposes the work required
to close it.

It is intentionally separate from the Credit Cards PRD because:
- The Credit Cards PRD is gated on client data sign-off and has a fixed
  end-July cutover.
- These items are larger, partly research, and span multiple verticals.
  Mixing them would compromise the Credit Cards cutover.

---

## 2. Strategy → capability map

The strategy doc names six capabilities and four data feeds. Here is what
exists in the repo today, and what does not.

### 2.1 Capabilities

| # | Strategy capability | What the strategy promises | What we have in the repo today | Gap |
|---|---|---|---|---|
| C1 | **Predictive RPC ("the engine")** | Per-click predicted £-value, used as a bid signal | `services/scoring-api` Rust hot-path, XGBoost on Vertex, `/v1/score` + `/v1/explain`, safety net, kill switch | **None.** This is V1, live on staging. |
| C2 | **gPS Cerberus — bot / IVT filter** | Real-time detection of bots and accidental taps; tells the bidder *not to learn from or pay for* the click | `cerberus_score` is consumed as an **input feature** of the RPC model (see `services/scoring-api/crates/domain/src/click.rs`, `dataform/definitions/training/rpc_training_rows.sqlx`). We assume the score arrives upstream. There is no detection service, no source of the score, no IVT enforcement decision. | Build (or integrate) the upstream score source, and add an enforcement decision separate from the RPC prediction. |
| C3 | **gPS Soteria — profit/margin lookup** | Bid on **profit**, not revenue. Commission tables per provider × product. | Reconciliation joins on `revenue` (`predictions_vs_revenue`). No commission table, no margin field anywhere in `dataform/`, `services/ml-pipeline/`, or the schemas. | New margin table + label change from `revenue` → `profit = revenue × margin_rate`. Re-train. |
| C4 | **gPS Phoebe — behavioural intent (GA4)** | Real-time signals from the on-site journey (calculators used, guides read, products compared) feeding the bid in-flight. | None. The click schema has `affinity_score`, `query_intent` (a single enum), `visits_prev_30d` — proxies, not the GA4 event stream. No GA4 ingestion. | New ingestion + feature store + serving-time enrichment. |
| C5 | **CRM / LTV layer** | Don't pay new-customer prices for existing customers; uplift bid when an existing single-product customer is shopping a second product. | No CRM ingestion. No hashed-identifier matching. Label is single-event RPC; no LTV head. | New CRM feed, matching layer, LTV model (or LTV head on the current model). |
| C6 | **Dynamic creative / value-tier output** | "High-Value Homeowner" → creative engine shows *Premium Home Protection* ad variant. | Output is a single scalar `predicted_rpc`. No value-tier bucketing, no creative-engine integration. | Add `value_tier` to the response contract + downstream creative-engine push. |
| C7 | **MMM halo (TV / print / radio)** | High-value-user temporal patterns fed into the offline media-mix model. | No export to MMM. No temporal-pattern aggregation by value tier. | Daily aggregate export by value tier × time-of-day × day-of-week. |
| C8 | **Multi-vertical** | Whole strategy is "MSM" — Loans, Life, Pet, Home, Car, Mortgage, Credit Cards. | Single schema. V2 is Credit-Cards-specific. No notion of `vertical_id` in the model, the API contract, the dashboard, or Terraform. | Per-vertical model registry + per-vertical reconciliation windows + dashboard vertical filter. |

### 2.2 Data feeds the strategy asks for

| # | Strategy feed | What we have | Gap |
|---|---|---|---|
| D1 | **Post-conversion sales data (GCLID ↔ final revenue, 12–24 months)** | `cm360_clicks_raw` + sales-ledger feed (Credit Cards-specific in V2). | **For Credit Cards only.** Per-vertical extension needed. |
| D2 | **GA4 / behavioural breadcrumbs** | Not ingested. | New ingestion pipeline (GA4 BigQuery export → staging view → feature store). |
| D3 | **Commission / margin tables** | None. | New reference table + change-data-capture process when provider rates change. |
| D4 | **CRM / loyalty file (hashed identifiers, tenure, multi-product flag)** | None. | New ingestion + matching service; PII inventory + ADR update. |

---

## 3. Goals and non-goals

### 3.1 In scope

1. **C2 Cerberus enforcement** — split bot detection from the RPC feature so we can refuse to learn from and refuse to pay for invalid traffic.
2. **C3 Soteria profit label** — train and serve on profit, not revenue. Commission table + label change + retrain.
3. **C4 Phoebe behavioural ingestion** — GA4 event stream → feature store → serving-time feature lookup.
4. **C5 CRM / LTV** — hashed-CRM ingestion, identifier match at scoring time, LTV head on the model.
5. **C6 Value-tier output** — segment predictions into tiers; add `value_tier` to `/v1/score` response.
6. **C8 Multi-vertical readiness** — `vertical_id` first-class in schema, model registry, dashboard, Terraform envs.

### 3.2 Should-have

7. **C7 MMM halo export** — daily aggregate to a BQ view consumable by the media-mix model.
8. **Creative-engine push** — value-tier → creative variant ID mapping (read-only on the creative side; we don't build creative).

### 3.3 Out of scope

- A new ML framework. Continue with XGBoost / Vertex.
- Customer-facing surfaces. ADR 0004 boundary still applies — bid-optimisation only.
- Real-time GA4 streaming below 60s latency (start with the GA4 BigQuery export, sub-hourly).
- Building the dynamic-creative engine itself. We expose the value-tier; the creative system already exists at MSM.
- Multi-touch attribution.

---

## 4. Architecture changes vs the current platform

V1 architecture is reused for: Cloud Run service shapes, Vertex hosting,
BQ raw→view materialisation, Pub/Sub topology, CD pipeline, safety net,
dashboard structure.

New components:

```
┌────────────────────────┐      ┌───────────────────────┐
│ GA4 BigQuery export    │─────▶│ phoebe-features view  │──┐
└────────────────────────┘      └───────────────────────┘  │
┌────────────────────────┐      ┌───────────────────────┐  │
│ CRM hashed-id feed     │─────▶│ crm-match service     │──┤
└────────────────────────┘      └───────────────────────┘  │
┌────────────────────────┐      ┌───────────────────────┐  │   ┌─────────────┐
│ Commission table CDC   │─────▶│ soteria-margin view   │──┼──▶│ scoring-api │
└────────────────────────┘      └───────────────────────┘  │   │  +value-tier│
┌────────────────────────┐      ┌───────────────────────┐  │   └──────┬──────┘
│ Click stream + IVT log │─────▶│ cerberus-decision svc │──┘          │
└────────────────────────┘      └───────────────────────┘             ▼
                                                              ┌───────────────┐
                                                              │ activation +  │
                                                              │ creative push │
                                                              └───────────────┘
                                                                      │
                                                                      ▼
                                                              ┌───────────────┐
                                                              │ MMM halo BQ   │
                                                              │ daily view    │
                                                              └───────────────┘
```

Concretely:

1. **New service `cerberus-decision`** (Rust, alongside `scoring-api`) returning `valid | suspect | invalid` for each click. `scoring-api` consults it pre-prediction; `invalid` short-circuits to `source = "REJECTED_IVT"` with `predicted_rpc = 0` and the click is excluded from training rows by the Dataform view.
2. **New service `crm-match`** (Python FastAPI) that maps a hashed identifier to `{is_known, tenure_days, product_count}`. Called from `scoring-api` enrichment step. Misses (~95%+) return `is_known=false` cheaply.
3. **New Dataform views**:
   - `phoebe_features` — per-cookie behavioural rollups from GA4 (calculator events, guide reads, compare-N).
   - `soteria_margins` — provider × product → margin rate.
   - `profit_training_rows` — replaces `rpc_training_rows`; label is `SUM(revenue × margin_rate)` over the reconciliation window.
   - `mmm_halo_daily` — daily aggregate `(vertical, value_tier, hour_of_day, dow) → clicks, profit, conversions`.
4. **Schema gains `vertical_id`** everywhere (`proto/`, `services/scoring-api/crates/domain`, `services/ml-pipeline`, `dataform/`, dashboard form).
5. **Model registry** moves from `rpc-estimator@N` to `rpc-estimator/<vertical>/@N`. Per-vertical traffic split and canary.
6. **LTV head** — second output of the model: `predicted_ltv_12m`. Used to compute `value_tier`.
7. **Response contract additions**:
   ```json
   {
     "predicted_rpc": 0.0,            // existing — profit-based when (3) lands
     "predicted_ltv_12m": 0.0,        // new
     "value_tier": "whale|porpoise|minnow|invalid", // new
     "ivt_decision": "valid|suspect|invalid",       // new
     "source": "MODEL|FALLBACK_*|REJECTED_IVT|KILL_SWITCH",
     "model_version": "rpc-estimator/credit-cards@3",
     "correlation_id": "..."
   }
   ```
8. **Activation extension**: pushes both `predicted_rpc` (to SA360/SSGTM/OCI as today) and `value_tier` (to the creative engine — new push target). Routing is per-vertical.
9. **Dashboard additions**:
   - Vertical selector (top of header).
   - Profit-vs-revenue toggle on KPI tiles.
   - Cerberus rejection rate panel + recent-rejection sample.
   - Value-tier distribution donut.
   - LTV head's calibration row in the model-health panel.
   - "MMM halo export freshness" pill.

---

## 5. Data contracts

A new `docs/data-contract-strategy.md` will pin the additions. Summary:

### 5.1 GA4 (Phoebe)

Source: GA4 BigQuery export, dataset `analytics_<property>`. We consume:
`event_name`, `event_timestamp`, `user_pseudo_id`, `event_params.page_path`,
`event_params.calculator_id`, `event_params.compare_count`,
`session_engagement_time_msec`. Aggregated nightly into `phoebe_features`
(cookie-level, 30-day rolling).

### 5.2 Commission / margin (Soteria)

```
provider_id          STRING REQUIRED
vertical_id          STRING REQUIRED
product_type         STRING REQUIRED
margin_rate          FLOAT64 REQUIRED [0..1]
effective_from       DATE REQUIRED
effective_to         DATE NULLABLE
```

Source: client finance team. CDC via a daily scheduled query that snapshots
the table; we keep an effective-dated history.

### 5.3 CRM (loyalty)

```
hashed_identifier    BYTES REQUIRED   -- SHA-256 of email; salt held client-side
vertical_id          STRING REQUIRED
first_purchase_date  DATE REQUIRED
product_count        INT64 REQUIRED
last_purchase_date   DATE REQUIRED
ltv_to_date          FLOAT64 REQUIRED
```

PII inventory: hashed identifier only. No plaintext PII ever enters the
platform. New row in the data-contract appendix; compliance sign-off is a
release gate.

### 5.4 Cerberus IVT log

```
click_id             STRING REQUIRED
correlation_id       STRING REQUIRED
decision_ts          TIMESTAMP REQUIRED
decision             STRING REQUIRED (valid|suspect|invalid)
rule_hits            ARRAY<STRING>    -- e.g. ["impossible_geo_velocity","headless_ua"]
confidence           FLOAT64 REQUIRED [0..1]
```

Persisted to BQ for auditability and for training the next-gen detector.

---

## 6. ML pipeline changes

### 6.1 Label change (Soteria)

`profit_training_rows.realized_label = SUM(revenue × margin_rate)` over the
reconciliation window. `rpc_training_rows` is kept for one model generation
so we can A/B revenue-trained vs profit-trained.

### 6.2 LTV head

Second target column on the same training row. Two strategies:
- **Multi-output XGBoost** (one model, two heads) — simpler, no extra
  endpoint.
- **Sibling model on the same endpoint** with `traffic_split` — easier to
  iterate.

Pick: **sibling model**. Lets us roll back LTV without affecting RPC.

### 6.3 Acceptance criteria additions

- LTV calibration: |mean(realized_12m_proxy − predicted_ltv_12m)| within
  20% of the per-vertical median LTV (full 12m label takes 12m — use a
  6m intermediate proxy for the first cut).
- Profit-trained model MAE within 25% of revenue-trained MAE *measured on
  profit*. (Beating it is the point, but we cap downside risk.)
- Value-tier confusion matrix stable across weeks — no tier should drift
  >10% in population share without an alert.

### 6.4 Cerberus model

Out of scope to train ourselves at MVP. We integrate the existing
Cerberus score source (per the strategy doc — "gPS Cerberus" is a Searce
product). If the source isn't ready, MVP uses a rules-only filter
(known-bad UAs, impossible velocity, abnormal CTR) wrapped in the
`cerberus-decision` service. The contract doesn't change either way.

---

## 7. Compliance and security

- **ADR 0005 (new)** — extends ADR 0004's boundary to the CRM and GA4
  feeds. Two invariants added:
  3. Hashed identifiers cannot be reversed by the platform; salt is held
     client-side and never crosses our network.
  4. GA4 PII (user IDs, ad IDs) is stripped at the staging view; only
     pseudo-IDs and event aggregates are retained.
- **ADR 0006 (new)** — value-tier output is informational. It may
  influence which **creative** a user sees but **never** affects
  product terms, pricing, or eligibility. (Restates ADR 0004 for the
  expanded surface.)
- **PII inventory** in `docs/data-contract-strategy.md §7` is the binding
  list. Sign-off by client compliance is a release gate per stream
  (Phoebe, CRM, Cerberus can land independently).

---

## 8. Operability

New alerts:

- Cerberus rejection rate > +50% week-over-week (signal of either an
  attack or an upstream change).
- Cerberus rejection rate < 0.1% over 24h (signal of a broken decision
  service — fail open is the wrong default for IVT).
- GA4 export freshness > 6h (Phoebe features become stale).
- Margin-table effective date in the past with no new row >7d.
- LTV head calibration drift > 25% week-over-week.

New runbooks:
- `cerberus-fail-open.md` — what to do when the decision service is
  degraded.
- `margin-table-refresh.md` — how to roll a commission update.
- `crm-rotation.md` — handling a salt rotation on the client side.
- `value-tier-cutoff-change.md` — how to re-bucket without retraining.

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Cerberus source not actually available; we own it | medium | high | Rules-only MVP under the same contract; replace transparently when source lands |
| Commission table changes mid-campaign cause label drift | high | medium | Effective-dated table; label uses effective rate at conversion time, not training time |
| CRM match rate is low (~2–5%) and the LTV uplift is marginal | medium | medium | Measure uplift on the matched cohort only; gate full rollout on that being a real number |
| GA4 export isn't sub-hourly; Phoebe is too stale to matter | medium | high | Start with nightly behavioural baseline + a serving-time "session intent" header from the bidder; upgrade to GA4 Realtime later |
| Value tier becomes a de-facto customer segmentation, breaching ADR 0004 spirit | medium | high | ADR 0006; activation push to creative engine is allowlisted to creative variant IDs only — no terms/pricing surface |
| Per-vertical models multiply ops cost | high | medium | One Vertex endpoint, multiple deployed models; per-vertical canary; shared monitoring |
| Multi-vertical roll-out competes with Credit Cards cutover | high | high | Sequencing in §10 keeps Credit Cards on its existing path |

---

## 10. Delivery plan

This is the **post-Credit-Cards** plan. Credit Cards cutover is now
**end-August 2026** (slipped from end-July to absorb Phoebe — see
`PRD-v2-credit-cards.md` §13). The work below starts the week after
that cutover.

**Re-plan note (2026-05-18):** the original S1 (vertical_id) was
already landed before this PRD was written — it shipped with the
CC schema migration. The original S4 (Phoebe) was pulled into the CC
MVP per the strategy day-one mandate. Phases below renumber: S1=Soteria,
S2=Cerberus, S3=CRM/LTV, S4=value-tier, S5=creative push + MMM,
S6=second vertical.

| Phase | Weeks | Deliverable | Gating |
|---|---|---|---|
| ~~S1 (done)~~ | — | ~~`vertical_id` plumbing~~ — landed in commit `0cb1d20` ahead of this PRD | — |
| S1 (was S2) | +3 | Soteria margin table + profit label + A/B retrain (Credit Cards first) | Client finance hands over commission table |
| S2 (was S3) | +3 | Cerberus decision service (rules MVP) + IVT log + dashboard panel | — |
| ~~S4 (Phoebe)~~ | — | ~~Phoebe GA4 ingestion + nightly features + serving lookup~~ — pulled into CC MVP per strategy mandate; see `PRD-v2-credit-cards.md` §2.1 item 8 | — |
| S3 (was S5) | +3 | CRM ingestion + matcher + ADR 0005 sign-off | Client legal + salt agreement |
| S4 (was S6) | +2 | LTV head trained, value-tier output added to `/v1/score`, dashboard donut | S1 + S3 |
| S5 (was S7) | +2 | Creative-engine push + MMM halo daily view | S4, client creative-engine API spec |
| S6 (was S8) | +3 | Second vertical (proposal: Loans) onboarded end-to-end | S1–S5 stable |

Rough total: **~16 weeks** from Credit Cards cutover to second vertical
live (was 22 — Phoebe consumed the 4 weeks for the strategy mandate,
vertical_id consumed 2). Assuming the gating items hold.

Engineering days remaining excluding waits: **~50 days** at one
full-time engineer, distributable across two engineers without
contention because S1/S2 are independent.

---

## 11. Acceptance criteria — Definition of done (V2 strategy alignment)

V2 strategy alignment is complete when **all** of:

1. `/v1/score` returns `predicted_rpc` (profit-based), `predicted_ltv_12m`,
   `value_tier`, `ivt_decision`, and `model_version` namespaced by
   vertical.
2. At least two verticals (Credit Cards + one of Loans / Home / Car) are
   live with their own deployed model and per-vertical reconciliation.
3. Cerberus decision service rejects measurable invalid traffic; the
   rejection rate panel on the dashboard shows a non-trivial volume; the
   rejected rows do not appear in `profit_training_rows`.
4. Soteria margin table is the source of truth for the label; revenue is
   retained as a parallel column but no longer the training target.
5. Phoebe nightly features are joined to clicks at training time and
   looked up at serving time; the dashboard's live-prediction form
   includes a "behavioural signal" group.
6. CRM matcher returns a non-zero match rate measured weekly; the LTV
   uplift on matched clicks is reported in the dashboard model-health
   panel.
7. MMM halo daily export is queryable by the media-mix model; the client
   media-planning team has confirmed it consumes the view.
8. Value-tier push to the creative engine is live and the creative team
   has acknowledged receipt for at least 7 consecutive days.
9. ADRs 0005 and 0006 are merged; PII inventory in
   `docs/data-contract-strategy.md` is signed.
10. Runbooks for §8 are rehearsed once.

---

## 12. Open questions (gated on client)

| ID | Question | Blocks | Owner |
|---|---|---|---|
| SQ-1 | Is gPS Cerberus a real product we can call, or do we build the rules MVP and replace later? | S3 | Searce / client |
| SQ-2 | Will client finance supply the provider × product margin table in the format in §5.2? Cadence of updates? | S2 | Client finance |
| SQ-3 | GA4 property and BigQuery export project — read access for the platform service account | S4 | Client analytics |
| SQ-4 | CRM hashed-identifier salt: who holds it, rotation cadence, how it's exchanged | S5 | Client engineering + legal |
| SQ-5 | Creative engine: API spec, value-tier → variant mapping, failure semantics | S7 | Client creative ops |
| SQ-6 | MMM consumer: which team / model, what schema do they want, refresh cadence | S7 | Client media-planning |
| SQ-7 | Vertical roll-out order after Credit Cards | S8 | Client product |
| SQ-8 | Is "value tier" a four-bucket scheme (whale/porpoise/minnow/invalid) or do they want a continuous percentile? | S6 | Client analytics |
| SQ-9 | Right-to-erasure on CRM hashed identifiers — SLA and propagation to derived features | Compliance | Client compliance |
| SQ-10 | Profit vs revenue activation: do bidders (SA360 etc.) want the profit number directly, or a normalised score? | S2 → activation | Client paid-media ops |

---

## 13. What this PRD does **not** do

It does not duplicate `docs/PRD-v2-credit-cards.md`. The Credit Cards
PRD's §4 (functional), §8 (ML pipeline), §10 (operability), §13 (delivery
plan) all stand. This document layers strategic capabilities on top of
that platform once it's running for one vertical.

It does not replace the original `Predictive RPC Estimator PRD.pdf`
(V1). The V1 RPC engine is the foundation everything here extends.

---

## 14. References

- `Predictive RPC Estimator PRD.pdf` — V1 product spec.
- `docs/PRD-v2-credit-cards.md` — single-vertical hardening PRD.
- `docs/SOW.md` — phase plan.
- `docs/data-contract.md`, `docs/data-contract-credit-cards.md` —
  existing contracts. `data-contract-strategy.md` (new) layers on top.
- `docs/adr/0003-credit-cards-conversion-reward.md` — sum-of-rewards
  conversion label; remains the right approach when the label becomes
  profit-based.
- `docs/adr/0004-fca-compliance-boundary.md` — boundary; ADRs 0005 and
  0006 extend it for CRM/GA4/value-tier.
- `Architectural Rules — 2026.md` — binding rules.
