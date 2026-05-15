# Credit Cards MVP — required changes to the platform

What's already in place (and reusable):
- End-to-end serving path: Cloud Run scoring API → Vertex AI → Pub/Sub → BigQuery → reconciliation → dashboard.
- Safety guardrails (bounds, clamp, timeouts, anomaly window, circuit breaker, kill switch).
- Model versioning + canary traffic-split machinery on the Vertex endpoint.
- Drift monitoring on inputs (PSI) and outputs (residuals) via Dataform.
- Live, explainable predictions in the executive dashboard.
- CD pipeline (`cd.yml`) building and deploying every service.

The architecture is product-agnostic; almost all the work below is **data
plumbing and domain-specific tuning**, not new services.

---

## 1. Feature schema (Rust + Python + BQ + dashboard)

The current 15-feature schema in `services/scoring-api/crates/presentation/src/main.rs`
(`ScoreRequest`) is generic. Credit Cards needs different inputs.

**Changes:**

- Replace / augment `query_intent` with a credit-cards-specific intent enum
  (e.g. `cashback`, `travel`, `balance_transfer`, `premium`, `student`,
  `business`, `secured`).
- Add **product type** as a top-level feature (the client may bid differently
  per card type).
- Replace `cerberus_score` (generic trust proxy) with credit-domain proxies
  the client actually has: approval-likelihood signal, prior-applicant flag,
  income-band bucket if available.
- Drop or rename `rpc_7d/14d/30d` to match the longer conversion windows
  (see §3).
- Add `affinity_score` derived from the query (e.g. "best cashback card" →
  high intent).

**Where it touches:**
- `services/scoring-api/crates/domain/` — `ClickFeatures` constructor
- `services/scoring-api/crates/presentation/src/main.rs` — `ScoreRequest`
- `services/ml-pipeline/` — training input schema
- `dataform/definitions/` — view that builds `rpc_training_rows`
- `proto/` — cross-service contracts
- `dashboard/src/presentation/App.tsx` — form fields and `labels.ts` translations

**Effort:** ~3-4 days for schema migration; the boundary-enforced layering
means changes propagate cleanly through the domain → adapters.

---

## 2. Reconciliation window — 30 days is wrong for Credit Cards

The current `predictions_vs_revenue` view uses
`predicted_at_ms + (30 * 24 * 60 * 60 * 1000)` as the window close.
Credit cards have a **multi-week-to-multi-month** consideration window:

| Event | Typical lag from click |
|---|---|
| Application submitted | hours-to-days |
| Application approved | days-to-weeks |
| Card activated | weeks |
| First eligible spend / interchange | 30-60 days |

**Changes:**
- Widen the reconciliation window to **90 days** (configurable per product).
- `predictions_vs_revenue` view: replace the hardcoded `30 *` with a
  parameter or per-product join.
- Dashboard: the "Settled at" column needs to be explicit that an
  unsettled click can be in flight for up to 90 days.
- `WINDOW_DAYS` constant in the React app needs a product-aware default.

**Where it touches:**
- `services/reconciliation/sql/predictions_vs_revenue.sql`
- `dashboard/src/presentation/App.tsx` (`WINDOW_DAYS`)
- `infra/terraform/envs/staging.tfvars` — new variable

**Effort:** half a day.

---

## 3. Multi-stage conversion / partial reward

Credit cards monetise across several events with different revenue values:

| Stage | Typical client value |
|---|---|
| Click → application started | small acquisition cost recovery |
| Application submitted | medium |
| Application approved | large |
| Card activated + first spend | full lifetime value share |

The current model assumes a single `realized_rpc` per click. We have two
options:

**Option A (simplest, recommended for MVP):** define `realized_rpc` as the
**total of all reward events** in the 90-day window for that click. The
sales-ledger ingestion sums multiple ledger rows into one click. The
model learns expected total value.

**Option B (later phase):** model each stage separately and combine
probability × value. Higher fidelity but requires three sub-models and
much more data.

Recommend Option A for the MVP, ADR the decision, revisit when coverage
is at 80% and we have richer signal.

**Where it touches:**
- `services/reconciliation/sql/predictions_vs_revenue.sql` — `SUM(revenue)`
  is already what's there; confirm semantics.
- `docs/adr/` — new ADR recording the choice.

**Effort:** half a day (mostly an ADR + a clarifying SQL comment).

---

## 4. 50% coverage handling

The 50% gap is the biggest unknown until we audit it. Add a small
coverage-audit pipeline that we can run on the first data sample.

**New:** `dataform/definitions/coverage_audit.sqlx`

Splits the 50% along the obvious dimensions (partner, channel, device,
card product, attribution window, day-of-week) and reports:

- Coverage % per slice
- Distribution skew vs the visible slice
- Conversion-time CDF on the visible slice
- A KS statistic or PSI-like score showing whether each slice's feature
  distribution differs from the population

Output goes to a new `dashboard` panel ("Where we have full visibility
vs where we don't") so we can show the client the missingness
characterisation visually.

**At training time:**
- Filter to rows with a known label (the 50%).
- Compute label-distribution by slice and inverse-propensity-weight
  training rows where missingness is informative.

**At serving time:**
- If the request lands in a slice with <X% historical coverage, log a
  `low_coverage_segment` warning and (optionally) defer to a
  deterministic fallback. Wired through the existing source-pill
  (`MODEL` vs `FALLBACK_*`).

**Where it touches:**
- `dataform/definitions/` — new audit views
- `services/scoring-api/crates/domain/` — new fallback branch
- `dashboard/` — new visualisation panel

**Effort:** ~3 days for the audit pipeline + visualisation; ~2 days for
the serving-side fallback if we decide we need it.

---

## 5. v1 → v2 canary path (existing machinery; just needs orchestration)

The platform supports this already (`gcloud ai endpoints update
--traffic-split`). What we need is the **runbook** and dashboard
support so the client can see both versions side-by-side.

**Changes:**
- Dashboard: when more than one `model_version` is observed in
  `rpc_predictions`, render a small **"Active versions"** panel
  showing each version's traffic share and rolling residual error.
- `docs/runbooks/canary-deploy.md` — concrete commands for traffic
  split, rollback, and the auto-rollback criteria (e.g. residual MAE
  drifts > 20% within 24 h).
- Add a Cloud Monitoring alert that fires if v2 residuals diverge.

**Effort:** ~2 days.

---

## 6. Client-isolated environment

We currently have `env = staging` and `env = prod` in Terraform. For a
client engagement we should add **`env = client-cc`** (or similar) with
its own:

- BigQuery dataset (`rpc_estimator_client_cc`)
- Vertex endpoint
- Service accounts
- WIF pool (or reuse staging's if the client GCP project is theirs)
- Image tags

**Where it touches:**
- `infra/terraform/envs/client-cc.tfvars` (new)
- `cd.yml` — add a `deploy-client-cc` job (or generalise the
  staging/prod pattern to N envs)

**Effort:** ~1 day if reusing our GCP project; ~2-3 days if the
client provides their own project (extra bootstrap, IAM, network).

---

## 7. Client data contract — Credit Cards specific

`docs/data-contract.md` is generic. We need a credit-cards-specific
contract covering:

- Click schema (fields, IDs, PII flagging, hashing)
- Sales-ledger schema (conversion stages, currency, refunds/charge-backs)
- Coverage trajectory (50% now → 80% by end-June → target)
- Refresh cadence (real-time vs batch)
- Retention and right-to-erasure handling
- The join key from clicks to sales (and what happens for cross-device)
- Sign-off block (data owner + engineering lead)

This is mostly a Confluence-style document with a checklist;
half a day to draft.

**New file:** `docs/data-contract-credit-cards.md`

---

## 8. Compliance framing (FCA)

We're scoring click value, not decisioning. That keeps us outside
SYSC 19A / Consumer Duty requirements that govern decisioning models.
Still worth:

- An ADR recording the boundary and the reasoning ("predictive RPC
  estimator does not influence the terms a customer is offered, only
  the bid we place for the click").
- A short PII inventory: what we ingest, where it lives, how long,
  who can access.

**Effort:** ~1 day.

---

## 9. Drift monitoring per segment

Current drift monitors operate on the full population. With 50% sales
coverage going to 80%, the population shifts as coverage changes —
that will look like drift even if nothing about the underlying clicks
is changing.

**Changes:**
- Segment the PSI / residual monitors by coverage-source so the
  monitor only fires on real distribution drift, not coverage drift.
- Add a "predicted-RPC vs realized-RPC by segment" panel to the
  dashboard so finance can spot product-type drift.

**Effort:** ~2 days.

---

## 10. Dashboard tweaks for the executive audience

The dashboard is product-agnostic today. Credit Cards needs:

- A **product-type filter** (dropdown at the top: All / Cashback /
  Travel / Balance transfer / etc.).
- A **window selector** (7 / 30 / 90 days) — defaulting to 90 to
  match the conversion window.
- A small **"Coverage today"** indicator next to the KPIs ("we have
  sales data for X% of clicks in this window").
- The live-prediction form needs the new feature schema (auto-renders
  from labels.ts).

**Effort:** ~2 days.

---

## Summary — prioritised by what's needed for MVP

| # | Change | Phase | Effort |
|---|---|---|---|
| 1 | Feature schema for Credit Cards | MVP | 3-4 days |
| 2 | Reconciliation window 30→90 days | MVP | 0.5 day |
| 3 | Multi-stage conversion (Option A) | MVP | 0.5 day + ADR |
| 4 | Coverage audit pipeline | MVP | 3 days |
| 6 | Client-isolated environment | MVP | 1-3 days |
| 7 | Credit-cards data contract | MVP | 0.5 day |
| 8 | Compliance framing (ADR + PII inventory) | MVP | 1 day |
| 10 | Dashboard tweaks (filter + window) | MVP | 2 days |
| 5 | v1→v2 canary visibility | Phase 2 | 2 days |
| 9 | Drift monitoring per segment | Phase 2 | 2 days |
| 4b | Serving-side low-coverage fallback | If audit says so | 2 days |

**Total MVP work (if 50% missingness turns out to be random):**
≈ 11–15 days of engineering, gated almost entirely on receiving the
data sample. The platform itself doesn't need new services.

**Total MVP work (if missingness is systematic):**
+ 5–7 days for the segment-aware ingestion fix and serving-side
fallback before training a useful model.

---

## What does NOT need to change

- Cloud Run service shapes (scoring-api, reconciliation, activation,
  breaker-automation, dashboard, ml-pipeline).
- Vertex AI hosting pattern.
- BigQuery topology and the raw → view materialisation pattern.
- The dashboard's general structure, interactive prediction panel,
  pipeline trace, attribution chart.
- The CD pipeline (just one new env config).
- The safety net (bounds / clamp / breaker / kill switch / anomaly).
- The deck.

In short: the platform was built to host this. The Credit Cards MVP
is data + tuning, not a rebuild.
