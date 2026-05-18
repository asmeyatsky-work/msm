# PRD V2 — Predictive RPC Estimator for Credit Cards

**Status:** Draft for build kickoff (re-planned 2026-05-18 — Phoebe in MVP)
**Author:** Allan Smeyatsky
**Date:** 2026-05-15 (re-plan 2026-05-18)
**Build start:** week of 2026-05-18
**Target MVP live:** 2026-08-31 (canary 100%) — slipped from 2026-07-31 to absorb Phoebe / GA4 ingestion
**Repo / V1 baseline:** `asmeyatsky-work/msm` @ `v0.1.9`

---

## 1. Executive summary

V1 of the Predictive RPC Estimator is operational on staging. It scores
generic clicks against an XGBoost model on Vertex AI, with a Rust hot-path
service on Cloud Run, BigQuery reconciliation, an executive dashboard with
live prediction + explainable AI, and a CD pipeline. It was demonstrated
to the client on **2026-05-12** and the client has confirmed they want
to proceed with a **Credit Cards** MVP.

V2 hardens the platform for a real client engagement against the
Credit Cards product line. The most consequential differences from V1:

| | V1 (synthetic) | V2 (Credit Cards) |
|---|---|---|
| Data | Synthetic seed (5k rows) | Real client click + sales-ledger feeds, 50% → 80% coverage by end of June 2026; **plus GA4 behavioural stream (Phoebe)** |
| Schema | Generic e-commerce features | Credit Cards-specific (product_type, stages, credit-domain proxies) **+ four Phoebe features** |
| Reconciliation window | 30 days | 90 days |
| Conversion model | Single-event RPC | Multi-stage sum-of-rewards (ADR 0003) |
| Environment | Single (`staging`) | Client-isolated (`client-cc`) + staging + prod |
| Model lifecycle | One version | v1 trained on 50%, v2 retrained on 80% with canary traffic split |
| Compliance | Demo-grade | FCA / Consumer Duty boundary documented and enforced (ADR 0004); GA4 PII boundary added (ADR 0005) |

End-to-end calendar from data-sample arrival is **~10 weeks** (was 8
before Phoebe was pulled in); aggressive **8 weeks**, conservative **12
weeks**. See §13 for the milestone plan.

Engineering remaining: **18–25 engineering days** (was 12–17 before
Phoebe), plus a conditional **+5–7 days** if the coverage audit reveals
systematic missingness, plus a conditional **+5 days** if the Phoebe
event taxonomy needs significant re-mapping against real GA4 rows
(OQ-12).

---

## 2. Goals and non-goals

### 2.1 In scope (must-have for MVP)

1. Real Credit Cards click + sales-ledger ingestion at the agreed
   schema (`docs/data-contract-credit-cards.md`).
2. A v1 model trained on the visible 50% of sales, deployed behind a
   canary, with calibration tracked daily on the visible slice.
3. Coverage-audit visibility on the dashboard so anyone — us or client —
   can see at any time which slices have full coverage and which don't.
4. The dashboard re-skinned for Credit Cards: product-type filter,
   90-day default window, Credit Cards features in the live-prediction
   form, plain-English explanation chart, model-health panel.
5. Client-isolated environment (`env = client-cc`) with its own GCP
   project (or namespace), Vertex endpoint, BigQuery dataset, Pub/Sub
   topics, service accounts, image tags.
6. v1 → v2 retrain and canary path exercised end-to-end with the
   dashboard showing each version's traffic share and rolling residual
   error.
7. Operability: per-segment drift monitoring, alerting tuned for
   Credit Cards-scale variance, runbooks updated.
8. **Phoebe behavioural features (GA4) — pulled into the MVP per the
   MSM Ads team strategy day-one mandate.** GA4 BigQuery export ingested,
   per-cookie behavioural rollup view (`phoebe_features`) joined to the
   training rows, four features available at scoring time via the
   existing feature-store adapter:
   - `phoebe_calculator_used` — whether the user interacted with an
     on-site APR / cashback calculator in this session.
   - `phoebe_guides_read` — count of credit-cards guide pages read in
     the rolling 30-day cookie window.
   - `phoebe_cards_compared` — count of distinct card products compared
     in the last 30 days.
   - `phoebe_session_engagement_s` — total engaged-session time (in
     seconds) over the rolling window.
   Refresh cadence is nightly at MVP (sub-hourly is the explicit
   follow-up — see §11 "Phoebe staleness" risk and ADR 0007). See
   §13 for the revised timeline.

### 2.2 In scope (should-have)

8. Production environment (`env = prod` for the client) provisioned
   from the same Terraform with parity of services, IAM, alerting, CD.
9. Right-sized Vertex AI machine for Credit Cards click volume.
10. Documented rollback plan rehearsed once before cutover.

### 2.3 Out of scope (will not deliver in V2)

- Net-new ML models beyond the existing XGBoost regressor.
- Multi-region active-active (single region `europe-west2` only).
- Customer-managed encryption keys (CMEK) unless the client mandates
  them post-data-contract.
- A consumer-facing product / personalised recommendation engine.
  V2 stays on the bid-optimisation side of the FCA boundary (ADR 0004).
- Migration of historical data older than the agreed contract window.
- Multi-touch attribution modelling. The model trains on
  click-id ↔ ledger-event joins as supplied; we do not infer
  cross-touch attribution.
- Per-stage sub-models (deferred to a V3 once 80% coverage is in
  place; ADR 0003 records the revisit trigger).

---

## 3. Users and use cases

| Persona | Need | Interaction surface |
|---|---|---|
| Client PPC bidding system | Get a predicted £-per-click value for every Credit Cards click, in <1s | `POST /v1/score` REST API |
| Client analyst / data team | Understand model accuracy on real data; spot drift early | Dashboard daily; BigQuery for ad-hoc |
| Client executive | Visualise platform value; demo-grade interactive prediction | Dashboard browser tab |
| Client compliance | Audit trail per prediction; PII handling evidence | BigQuery audit views + ADR 0004 |
| Client on-call | Diagnose alerts; flip kill-switch; roll back a model version | Cloud Console + runbooks in `docs/runbooks/` |
| Searce platform engineer | Ship code, run canaries, retrain | GitHub Actions CD + `ops/owner-actions.sh` |

---

## 4. Functional requirements

### 4.1 Scoring API

- `POST /v1/score` accepts the Credit Cards-specific click context (§7.1)
  and returns `predicted_rpc`, `source` (`MODEL` / `FALLBACK_*` /
  `KILL_SWITCH`), `model_version`, `correlation_id` in JSON.
- `POST /v1/explain` accepts the same payload and returns `base_value`
  plus a list of `[feature_name, attribution]` pairs. Feature names
  use the engineering identifiers (the dashboard humanises them).
- Both endpoints respond within **2 s p95** end-to-end at expected
  load. Hot-path service is Rust on Cloud Run (`scoring-api`),
  Vertex AI hosts the XGBoost model.
- Safety net (PRD V1 §5; carried over):
  - Prediction bounds (per-segment min/max; rejected predictions
    fall back to the deterministic source).
  - Negative-prediction clamp.
  - Model and BigQuery timeouts, configurable per env.
  - Anomaly detection window — null/zero-rate threshold, breaker on
    breach.
  - Single kill-switch flag (no redeploy).

### 4.2 Reconciliation API

- `GET /reconciliation?start=<ms>&end=<ms>` returns reconciled rows
  from the `predictions_vs_revenue` view for windows that closed
  inside `[start, end]`.
- Window length is **90 days** for the Credit Cards env
  (`reconciliation_window_days = 90` in Terraform).
- Optional `product_type=<value>` query parameter filters rows by
  Credit Cards product.

### 4.3 Coverage-audit API

- `GET /coverage` returns, per slice and overall:
  - `clicks_in_window`
  - `clicks_with_revenue`
  - `coverage_rate`
- Backed by the `coverage_audit` Dataform view
  (`dataform/definitions/monitoring/coverage_audit.sqlx`).
- The dashboard renders this as a "Where we have full visibility"
  panel above the residual chart.

### 4.4 Activation

- `activation-staging` continues to push predictions to SA360 / SSGTM
  / OCI. No code changes for V2 — but the Credit Cards env may want
  product-type-aware routing (logged but deferred).

### 4.5 Dashboard

- Header: client logo / title, env pill, **product-type filter**,
  **7 / 30 / 90-day window selector** (default 90 for Credit Cards).
- KPI tiles (plain-English copy already shipped in V1.1):
  - Clicks scored & checked
  - Avg. earning we expected
  - Avg. earning we actually got
  - Typical error per click + bias direction
  - Clicks that converted
- Coverage panel (**new in V2**): "Where we have full visibility" —
  bar chart of coverage % by slice with the dimensions from
  `coverage_audit.sqlx`. Red bars for slices below an agreed threshold
  (e.g. < 60%).
- Daily forecast-vs-reality chart with a `product_type` dropdown
  re-segmenting the lines.
- Source mix donut.
- Residual histogram.
- "What's running behind the dashboard" — model-health pills.
- **Active versions panel (new in V2)**: when more than one
  `model_version` is observed, shows each version's traffic share,
  rolling MAE, and how many days it has been live.
- Live prediction card with Credit Cards form fields and humanised
  explanation chart.
- "Recent predictions, settled" table.

### 4.6 Operability

- Cloud Monitoring alerts (V1 carried over, thresholds re-tuned for
  Credit Cards):
  - Scoring API p95 latency > 1500 ms over 5 min.
  - Error rate > 1% over 5 min.
  - Breaker trip rate > 0 in 1 h.
  - Anomaly window active.
- New for V2:
  - Per-segment residual MAE drift > 25% week-over-week, alerts on
    the product_type, geo, or device that's drifting.
  - Coverage drop > 10% week-over-week on any slice.
- Email notification channel already provisioned; PagerDuty / Slack
  routes added on request.

---

## 5. Non-functional requirements

| Class | Requirement |
|---|---|
| **Latency** | `POST /v1/score` p95 ≤ 1500 ms; p99 ≤ 2500 ms in the Credit Cards env (re-baselined after first real load). |
| **Availability** | 99.5% over a rolling 30 days on the scoring path. Dashboard 99.0%. |
| **Throughput** | Initial sizing: 100 req/s sustained, 300 req/s burst. Re-sized once client provides actual click volume by `product_type` (open question OQ-3). |
| **Cold-start** | `min_instances = 1` on scoring-api, reconciliation, dashboard in the Credit Cards env (cost ≈ £4/day). Vertex endpoint also min=1, on a machine sized from the load profile. |
| **Data residency** | All data resident in `europe-west2` (London). No US-region replicas. No CMEK by default; available on request. |
| **Retention** | Predictions retained 180 days at row level; aggregates indefinitely. Sales-ledger retained per client retention policy. Right-to-erasure on a `click_id` deletes from `rpc_predictions_raw` and `cm360_clicks_raw`. |
| **Auth** | Workload Identity Federation for CI; no long-lived service-account keys. Cloud Run services are public-unauthenticated **only on the staging env**; client env tightens to authenticated via IAP or LB once the bidding system is in place. |
| **Compliance** | ADR 0004 boundary enforced. Sign-off from client compliance contact on §6 of `data-contract-credit-cards.md` is a release gate. |
| **Encryption** | Google-managed keys at rest and in transit by default. |
| **Supply chain** | Container images pinned by digest; `cargo-deny`, `pip-audit`, `npm audit` gates on every PR. SBOM published per release. |
| **Audit** | Every prediction logged with `model_version`, `source`, input features (subject to PII inventory), output, latency, correlation ID. |

---

## 6. Architecture changes vs V1

V1 architecture is reused unchanged for: Cloud Run service shapes,
Vertex AI hosting pattern, BigQuery raw→view materialisation,
Pub/Sub topology, CD pipeline, safety net, executive dashboard
structure.

V2 changes:

1. **New Terraform env `client-cc`** in `infra/terraform/envs/client-cc.tfvars`:
   - GCP project (TBD: client's own or namespace in `msm-rpc`).
   - `reconciliation_window_days = 90`.
   - `anomaly_threshold = 0.03` (production-grade).
   - `model_timeout_ms`, `bq_timeout_ms` tuned from first load profile.
   - `scoring_api_*` sizing from client volume.
   - `dashboard_min_instances = 1`, `reconciliation_min_instances = 1`.
2. **Updated `cd.yml`** with a `deploy-client-cc` job mirroring `deploy-staging`
   with `client-cc` env name and its own state bucket.
3. **Coverage-audit view** (`dataform/definitions/monitoring/coverage_audit.sqlx`)
   landed in V1 phase-1; consumed by the dashboard in V2.
4. **`predictions_vs_revenue` view** is now a Terraform resource using
   `var.reconciliation_window_days` — V1 phase-1 landed this.
5. **Feature schema migration** end-to-end:
   - `proto/` cross-service contract (if used).
   - `services/scoring-api/crates/domain/ClickFeatures` constructor.
   - `services/scoring-api/crates/presentation/ScoreRequest`.
   - `services/ml-pipeline/` training input schema.
   - `dataform/definitions/training/rpc_training_rows.sqlx`.
   - `dashboard/src/presentation/App.tsx` form fields.
   - `dashboard/src/presentation/labels.ts` humanisation.
   - **`vertical_id` added as a top-level required field** across every
     layer above. For Credit Cards MVP the only emitted value is
     `"credit_cards"`, but the column, proto field, request param, view
     column, and model registry namespace
     (`rpc-estimator/credit-cards@N`) are all in place so a second
     vertical does not trigger a second cross-cutting migration. Cost
     here is ~half a day on top of the CC schema work; deferring it
     costs the same migration twice.
6. **Active-versions dashboard panel** for the canary path.

---

## 7. Data model

### 7.1 Click feed

Per `docs/data-contract-credit-cards.md §3`. New fields vs V1
(Credit Cards-specific in **bold**):

```
click_id              STRING REQUIRED
correlation_id        STRING REQUIRED
click_ts              TIMESTAMP REQUIRED (partition)
**vertical_id**       STRING REQUIRED (always "credit_cards" at MVP; reserved for multi-vertical roll-out)
device                STRING REQUIRED
geo                   STRING REQUIRED
hour_of_day           INT64 REQUIRED
**product_type**      STRING REQUIRED (cashback / travel / balance_transfer / premium / student / business / secured)
**card_product_id**   STRING REQUIRED
**query_intent**      STRING REQUIRED (compare / shop / apply / research / navigational)
**affinity_score**    FLOAT64 REQUIRED [0..1]
ad_creative_id        STRING REQUIRED
**prior_applicant**   BOOL   REQUIRED (cookie-level, never customer)
**income_band_bucket** STRING NULLABLE (low / mid / high / NULL)
auction_pressure      FLOAT64 REQUIRED [0..1]
**rpc_14d**           FLOAT64 REQUIRED ≥0 (rolling, per product_type)
**rpc_60d**           FLOAT64 REQUIRED ≥0 (rolling, per product_type)
landing_path          STRING REQUIRED (no querystring, no PII)
visits_prev_30d       INT64  REQUIRED ≥0 (cookie-level)
**phoebe_calculator_used**     BOOL    REQUIRED  (Phoebe / GA4)
**phoebe_guides_read**         INT64   REQUIRED ≥0 (Phoebe / GA4, 30d rolling)
**phoebe_cards_compared**      INT64   REQUIRED ≥0 (Phoebe / GA4, 30d rolling)
**phoebe_session_engagement_s** FLOAT64 REQUIRED ≥0 (Phoebe / GA4, 30d rolling, seconds)
```

**Removed** (e-commerce proxies that don't map):
`cerberus_score`, `rpc_7d`, `rpc_30d`, `is_payday_week`.

### 7.2 Sales-ledger feed

```
ledger_event_id  STRING REQUIRED (unique per row)
click_id         STRING REQUIRED (joins click feed)
event_ts         TIMESTAMP REQUIRED (partition)
**stage**        STRING REQUIRED (application_started / application_submitted / approved / activated / first_spend / chargeback)
revenue          FLOAT64 REQUIRED (signed; negative for chargebacks)
**margin_rate**  FLOAT64 NULLABLE  [0..1]  -- COALESCEs to 1.0 in the label view until Soteria delivers
currency         STRING REQUIRED (GBP only at MVP)
card_product_id  STRING REQUIRED
```

### 7.3 Derived views

- `cm360_clicks` (typed from `cm360_clicks_raw`).
- `rpc_predictions` (typed from `rpc_predictions_raw`).
- `predictions_vs_revenue` — joined view; 90-day window; one row per
  click; `realized_rpc = SUM(revenue * COALESCE(margin_rate, 1.0))`
  over the window (ADR 0003). The `margin_rate` column is added to the
  sales-ledger feed as **NULLABLE FLOAT64** for the CC MVP; while the
  client has not supplied a commission table, all rows coalesce to 1.0
  and `realized_rpc` equals `SUM(revenue)` (V1 behaviour, unchanged).
  Once a margin table is delivered, populating `margin_rate` is a
  data-only change — no view rewrite, no schema migration, and the
  existing model can be retrained against the new label without
  touching the API contract.
- `rpc_training_rows` — features joined to labels, used by the
  training pipeline.
- `coverage_audit` — sliced coverage %.
- `phoebe_features` — per-cookie GA4 behavioural rollup, joined into
  `rpc_training_rows` and looked up at scoring time via the existing
  feature-store adapter. Source: GA4 BigQuery export, dataset
  `analytics_<property>`. Refresh cadence: nightly (sub-hourly is a
  documented follow-up).

---

## 8. ML pipeline

### 8.1 Training (Vertex AI Pipelines)

- Input: `rpc_training_rows` view filtered to known labels (the
  visible 50% → 80%).
- Model: XGBoost regressor (continuity with V1).
- Hyperparameters carried from V1, re-tuned post-first-train.
- Train/validation split: time-based, last 14 days held out.
- Output: model artifact in `gs://<client-bucket>/models/rpc-estimator/<ts>/`
  registered as `rpc-estimator@N` in Vertex Model Registry, with
  `explanationSpec` (sampled-Shapley, paths=10) so `/v1/explain` works.

### 8.2 Evaluation

Acceptance criteria for a new model version before canary:

- MAE on held-out converters within 25% of the current production model
  (or, for v1 against the baseline, within 25% of the median ledger
  revenue for the product).
- No segment (product_type × device × geo) where MAE doubles vs overall.
- Bias |mean(realized − predicted)| < £0.30 across the held-out window.
- Calibration: residuals approximately symmetric around zero per
  product_type.

### 8.3 Deployment — canary

1. Register new model in Vertex Model Registry.
2. Deploy to existing endpoint with `traffic_split = 10`.
3. Watch dashboard `active versions` panel for 24 hours:
   - No breaker trips on the new version.
   - Per-version MAE within ±20% of incumbent.
4. Step to 50% for 24 hours.
5. Step to 100%. Decommission previous deployed model.
6. Rollback at any step: traffic_split back to 0 on the new version.

---

## 9. Compliance and security

- **ADR 0004** is binding: this is a bid-optimisation model, not a
  decisioning model. Two invariants:
  1. No customer-facing identifiers ingested.
  2. No model output forwarded to anything that affects customer
     terms.
- **PII inventory** in `docs/data-contract-credit-cards.md §6` is the
  authoritative list of what we ingest. Sign-off by client compliance
  is a release gate.
- **Auditability**: every prediction has a `correlation_id` tracing it
  end-to-end. `rpc_predictions` retains it for 180 days.
- **Service accounts** per service, least-privilege, encoded in
  Terraform. WIF only — no service-account keys.
- **Secret rotation** runbook covers Vertex endpoint creds, BigQuery
  service account, and any client-issued credentials.
- **Supply-chain gates** run in CI on every PR.

---

## 10. Operability

- SLOs in §5; alert policies in `infra/terraform/monitoring.tf`.
- Runbooks under `docs/runbooks/`:
  - `breaker-reset.md`
  - `canary-deploy.md` (updated for v1→v2)
  - `model-rollback.md` (Vertex traffic-split)
  - `endpoint-scale-down.md` (cost defence after handover)
  - `secret-rotation.md`
  - `bq-schema-migration.md`
  - `coverage-audit.md` (**new for V2**)
- Cloud Logging + Trace + Monitoring on every Cloud Run service.
- Reconciliation latency: predictions visible in `rpc_predictions`
  within < 5 min; reconciliation-vs-ledger refreshed continuously
  via the BigQuery view (no schedule).

---

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Missing 50% is systematic, not random | medium | high | Coverage audit on first sample; segment-aware fallback in serving if systematic; client-side ingestion fix scoped into the schedule. |
| Real Credit Cards click volume exceeds load-profile assumptions | medium | medium | Pre-size from client volume estimate (OQ-3); Vertex AI scales horizontally; load test before cutover. |
| 90-day window leaves long pending tail; first-month residual chart is sparse | high | low | Communicate in dashboard copy; KPI tiles show "still in flight" alongside "settled"; daily MAE on settled clicks only. |
| Sales-ledger join key has lower fidelity than the click ID | medium | high | Data contract sign-off explicitly names the join key (§3); pilot validation on first sample. |
| Stage-mix shifts across campaigns; the sum-of-rewards label calibration drifts | medium | medium | Per-stage volume mix on the drift dashboard; revisit per-stage sub-models (V3) when shift exceeds a threshold. |
| FCA boundary creep — product asks to add personalisation later | medium | high | ADR 0004 lists the two invariants; any change triggers a new ADR + compliance review before merge. |
| Client GCP project bootstrap drags | low | medium | Reuse `msm-rpc` with namespaced datasets/services as a fallback. |
| pip-audit / cargo-deny / npm audit churn during build (V1 already hit this) | medium | low | Workflow already auto-upgrades pip; routine triage. |
| **GA4 access not granted in week 1 (OQ-11)** | medium | **critical** | This is now the single biggest cutover risk. Daily check-in with client analytics until granted. If it slides past week 2 we re-open the deferral conversation (option B of the Phoebe-in-MVP decision). |
| **Phoebe event taxonomy doesn't match the strategy doc's bullets** | medium | high | Week-2 schema-discovery on real GA4 rows; +1 week buffer reserved. The four features in §7.1 are best-current-guess and may need renaming or re-mapping. The schema migration code is structured so adding/removing a Phoebe field is mechanical. |
| **Phoebe staleness — nightly rollup misses in-session intent** | medium | medium | MVP ships nightly; the dashboard surfaces "phoebe freshness" so we can see when the rollup stale; sub-hourly rollup is the documented follow-up (ADR 0007). |
| **GA4 PII exposure** | low | high | Hashed `user_pseudo_id` only; raw `user_id` and `ga_session_id` stripped at the staging view; ADR 0005 (new). Client compliance signs off the GA4 PII inventory in `data-contract-phoebe.md`. |

---

## 12. Acceptance criteria — Definition of done

V2 is complete when **all** of the following are true:

1. `client-cc` env serves `/v1/score` and `/v1/explain` against
   `rpc-estimator@2` trained on real Credit Cards data with 80%
   coverage, with all PRD §5 guardrails active.
2. Dashboard at the client-iso URL shows real reconciliation rows in
   the 90-day window, the coverage panel reflects the latest audit,
   the active-versions panel shows v2 at 100% and v1 decommissioned.
3. Per-segment drift monitors and Cloud Monitoring alerts are wired
   to the client's notification channel.
4. Runbooks rehearsed once each with the client on-call.
5. Rollback to v1 has been dry-run in a low-traffic window and
   documented.
6. Client compliance contact has signed `data-contract-credit-cards.md
   §8`.
7. Client engineering lead and data owner have signed off on the
   handover.

---

## 13. Delivery plan

Calendar plan assumes today (**2026-05-15**) is week 0. Weeks count
from the **data-sample arrival**, not from kickoff — the timeline is
gated on data delivery.

**Re-plan note (2026-05-18):** Phoebe (GA4 behavioural features) was
pulled into the MVP per the MSM Ads team strategy day-one mandate. This
adds three weeks to the original end-July cutover — new target is
**end-August 2026**. The slip is driven by GA4 access + schema-discovery
time, not by additional engineering on the platform: see Weeks 2-3 below.

### Week 1 (≈ 18–22 May 2026)
- Kick-off call, sign-off on this PRD V2.
- Data contract circulated for client legal + compliance.
- GCP project decision (client's vs `msm-rpc` namespace).
- Feature schema migration starts in `scoring-api`, `ml-pipeline`,
  dashboard (against the documented schema; no data needed yet) — this
  now includes the four Phoebe fields.
- Coverage-audit view extended for dashboard consumption.
- **GA4 access request submitted** to client analytics (OQ-3 elevated
  to week-1 critical; without it the entire MVP slips).

### Week 2
- Data contract signed; first data sample lands in BigQuery (~30 days,
  ~100k rows).
- Coverage audit run on the sample. **Decision point**: random vs
  systematic missingness.
  - Random → proceed.
  - Systematic → scope segment-aware fallback (+5–7 days, runs in
    parallel with v1 training).
- Client-iso Terraform env stood up (`client-cc`), CD wired, first
  no-op deploy green.
- **GA4 export access granted** — the platform SA reads
  `analytics_<property>` in the client's GA4 BigQuery project.
- **Phoebe schema discovery**: capture which `event_name` values are
  actually emitted, validate the four feature mappings hold against
  real GA4 rows.

### Week 3
- Real ingestion live (Pub/Sub → BQ for clicks; scheduled query for
  ledger).
- **`phoebe_features` view live**: nightly per-cookie rollup from GA4
  events, joined into `rpc_training_rows` and pushed to the feature
  store for serving-time lookup.
- v1 trained on 50% sample **including Phoebe features**.
- v1 evaluated against §8.2 acceptance criteria.
- Dashboard product-type filter, coverage panel, active-versions
  panel landed.

### Week 4
- v1 deployed to canary 10% on client env.
- Daily calibration tracked on visible 50%.
- **Phoebe-lift A/B**: a no-Phoebe model is also registered (same
  features minus the four Phoebe columns) to quantify the behavioural
  uplift before any client conversation about Phoebe ROI.
- Runbooks rehearsed.

### Week 5
- v1 stepped to 100% on client env (still a learning environment).
- Monitoring tuned from real traffic; alert thresholds calibrated.
- Per-segment drift monitors live (now sliced by `phoebe_calculator_used`
  too — researchers vs appliers).

### Week 6 — end-June
- Client delivers 80% coverage data.
- v2 retrained on the larger labelled set + the now-richer Phoebe
  history.
- v2 evaluated; sign-off for canary.

### Week 7
- v2 canary 10% → 50% over 48h on client env.
- Active-versions dashboard shows both running with their MAE.

### Week 8 — end-July (was original cutover; now mid-flight)
- v2 reaches 100% traffic on the client env.
- Soak — collect a full week of real Phoebe-on traffic before handover.

### Week 9-10 — end-August
- v1 deployment removed from the Vertex endpoint.
- Handover sign-off (§12 ticked off in full).

### Buffers
- +5–7 days for systematic missingness (between week 2 and week 3).
- +2–3 days for prod GCP project bootstrap if separate from `msm-rpc`.
- +1 week for client-side legal review beyond expectation.
- +1 week reserved for Phoebe schema mismatches discovered against real
  GA4 rows (the four MVP features are best-current-guess from the
  strategy doc; real events may need re-mapping).

---

## 14. Open questions (gated on client)

Tracked here so we don't lose them. Each blocks something.

| ID | Question | Blocks | Owner |
|---|---|---|---|
| OQ-1 | GCP project: client's own or namespace in `msm-rpc`? | Week 1 env bootstrap | Client IT + Searce |
| OQ-2 | Compliance contact for ADR 0004 / data-contract §6 sign-off | Week 2 release gate | Client compliance |
| OQ-3 | Estimated Credit Cards click volume per product_type per day | Vertex sizing in week 2 | Client analytics |
| OQ-4 | Sales-ledger join key — `click_id` from CM360 export, or hashed customer reference? | Week 1 schema validation | Client engineering |
| OQ-5 | Conversion definition: same-session, multi-touch, or last-touch? | Affects label semantics; ADR may need revisit | Client analytics |
| OQ-6 | Will the missing 50% pattern be characterised before sample delivery, or do we discover it in the audit? | Week 2 decision point | Client data |
| OQ-7 | Real-time vs batch sales-ledger refresh — hourly is the assumed cadence; is sub-hourly available? | Drift monitor latency | Client engineering |
| OQ-8 | Right-to-erasure SLA for `click_id` deletions | Retention policy | Client compliance |
| OQ-9 | Two named contacts (data owner + engineering lead) | Working sessions throughout | Client |
| OQ-10 | Production traffic on the client side: which bidder, which platform (SA360 / direct), failure semantics | Activation integration | Client engineering |
| **OQ-11** | **GA4 BigQuery export — read access for the platform SA on `analytics_<property>` dataset; which property covers Credit Cards traffic; retention** | **Week 1 — without this the whole MVP slips, this is the new critical-path gate** | **Client analytics** |
| **OQ-12** | **GA4 event taxonomy on the MSM site — which `event_name` values map to "calculator used", "guide read", "card compare"? The four Phoebe features in §7.1 are best-current-guess from the strategy doc and must be validated against real events** | **Phoebe schema discovery in week 2** | **Client analytics + Searce** |
| **OQ-13** | **Click→cookie join key — how does `user_pseudo_id` arrive on the click payload? Server-side CM360+GA4 merge, first-party-cookie pass-through, or no join (Phoebe defaults for all)?** | **Phoebe serving-time lookup** | **Client engineering** |

---

## 15. References

Documents in this repo that V2 depends on:

- `Predictive RPC Estimator PRD.pdf` — original product spec.
- `Architectural Rules — 2026.md` — hard architectural rules.
- `docs/SOW.md` — Phase 1 / 2 / 3 plan from V1.
- `docs/data-contract.md` — generic data contract V2 extends.
- `docs/data-contract-credit-cards.md` — Credit Cards-specific addendum
  (binding for V2).
- `docs/adr/0001-stack-and-activation.md` — stack choices.
- `docs/adr/0002-explain-path.md` — explanation path.
- `docs/adr/0003-credit-cards-conversion-reward.md` — sum-of-rewards
  choice for the MVP.
- `docs/adr/0004-fca-compliance-boundary.md` — Consumer Duty boundary.
- `docs/credit-cards-mvp-changes.md` — engineering change plan that
  drove this PRD.
- `docs/runbooks/` — operational runbooks.
- `docs/client-demo-deck.pptx` — V1 demo deck (still used for the
  initial client conversation).

---

## 16. Appendix — what V1 already provides (do not rebuild)

These are reusable as-is. Do not touch in V2 unless a specific
requirement above calls for it.

- `services/scoring-api` — Rust hot-path service, guardrails, breaker
  pattern, anomaly window, kill-switch.
- `services/reconciliation` — Python FastAPI reading
  `predictions_vs_revenue`.
- `services/activation` — Python push to SA360 / SSGTM / OCI.
- `services/breaker-automation` — anomaly event → breaker config update.
- `services/ml-pipeline` — Vertex AI Pipelines training job.
- `services/bounds-calibration` — per-segment RPC bounds job.
- `dashboard/` — React + nginx single-page app with live prediction
  panel, backend pipeline trace, attribution chart, plain-English copy.
- `infra/terraform/` — Cloud Run, BQ, Pub/Sub, Vertex SA grants, WIF,
  Cloud Monitoring alerts.
- `.github/workflows/cd.yml` — build + push + deploy with import
  fallback for pre-existing services.
- `.github/workflows/ci.yml` — Rust + Python + TS + supply-chain
  gates.
- `dataform/definitions/` — drift monitors and training-rows view.
- `mcp-servers/` — engineering tooling per bounded context.

V2 inherits all of this. The engineering work is **migration and
tuning of an existing platform** to a specific product (Credit Cards),
not a rebuild.
