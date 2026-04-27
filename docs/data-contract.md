# Data Contract — Predictive RPC Estimator

**Status:** Draft for client sign-off
**Owner (us):** scoring-platform team
**Owner (client):** [name TBD]
**Target:** Phase 2.2 ingestion goes live within 5 business days of this doc being signed.

---

## 1. Why this contract exists

The model trained from `v0.1.5` was fit on 5,000 synthetic rows (`ops/seed_synthetic_data.sql`). The math is meaningful but the signal isn't — it doesn't reflect real ad traffic. To complete Phase 2 of the SOW we need real **clicks** and a real **sales ledger** in BigQuery. This document fixes the schema, freshness, and PII rules between client systems and `rpc_estimator_staging`.

If anything below is wrong, this is the place to push back — once signed, every downstream artefact (ingestion, training, drift monitors, prod cutover) is built against it.

## 2. Datasets

Two feeds, both landing in `msm-rpc.rpc_estimator_staging`:

### 2.1 `clicks` — every click that should be scoreable

Replaces `synthetic_clicks`. Append-only.

| Column            | Type        | Mode     | Notes |
|-------------------|-------------|----------|-------|
| `click_id`        | STRING      | REQUIRED | Stable, globally unique. We hash this for canary stickiness, so it must not be reused. |
| `click_ts`        | TIMESTAMP   | REQUIRED | When the click happened. UTC. Partition column. |
| `device`          | STRING      | REQUIRED | One of `mobile`, `desktop`, `tablet`. Other values become `unknown` at ingest. |
| `geo`             | STRING      | REQUIRED | ISO-3166-1 alpha-2 country (`GB`, `US`, …). Two letters, uppercase. |
| `hour_of_day`     | INT64       | REQUIRED | `0..23`, derived from `click_ts` in the click's local TZ. |
| `query_intent`    | STRING      | REQUIRED | One of `commercial`, `informational`, `navigational`. |
| `ad_creative_id`  | STRING      | REQUIRED | Stable creative ID (matches the client's CM360 export). |
| `cerberus_score`  | FLOAT64     | REQUIRED | Fraud/quality score in `[0.0, 1.0]`. Higher = better. |
| `rpc_7d`          | FLOAT64     | REQUIRED | Rolling RPC over the prior 7 days for this click's segment. ≥ 0. |
| `rpc_14d`         | FLOAT64     | REQUIRED | 14-day window, ≥ 0. |
| `rpc_30d`         | FLOAT64     | REQUIRED | 30-day window, ≥ 0. |
| `is_payday_week`  | BOOL        | REQUIRED | Calendar flag the client computes. |
| `auction_pressure`| FLOAT64     | REQUIRED | `[0.0, 1.0]` — relative auction depth at click time. |
| `landing_path`    | STRING      | REQUIRED | Path component only (no host, no querystring). |
| `visits_prev_30d` | INT64       | REQUIRED | Visits by this user/cookie in the prior 30 days. ≥ 0. |

### 2.2 `sales_ledger` — realised revenue per click

Already exists with the schema below; production data merges in via Phase 2.2 ingestion.

| Column        | Type      | Mode     | Notes |
|---------------|-----------|----------|-------|
| `click_id`    | STRING    | REQUIRED | FK to `clicks.click_id`. |
| `revenue`     | FLOAT64   | REQUIRED | Realised gross revenue for that click, in GBP. ≥ 0. Refunds/chargebacks reverse the row (see §5). |
| `revenue_ts`  | TIMESTAMP | REQUIRED | When the revenue was attributed (post-conversion). UTC. Partition column. |
| `order_id`    | STRING    | NULLABLE | Client's order ID; NULL for non-monetised conversions. |
| `ts_ms`       | INT64     | NULLABLE | Mirror of `revenue_ts` in epoch-ms (legacy field, optional). |

Not every click has a ledger row — non-converters are absent, not zero-revenue rows.

## 3. Freshness & cadence

| Feed           | Latency target           | Cadence              | Mechanism (proposed)                   |
|----------------|--------------------------|----------------------|----------------------------------------|
| `clicks`       | ≤ 30 minutes from event  | Continuous           | Pub/Sub → BigQuery streaming insert    |
| `sales_ledger` | ≤ 6 hours from order     | Hourly batch         | GCS export → scheduled query, or direct |

Hard floors below which we'll alert:
- `clicks`: no rows in any 15-minute window during 06:00–22:00 UTC.
- `sales_ledger`: no rows in any 12-hour window. Quieter overnight is fine.

## 4. Identity, PII, and access

- `click_id`, `ad_creative_id`, `landing_path`, and `order_id` are **not** PII as far as our pipeline is concerned. None of the columns above carry email, name, IP, device ID, or raw query text.
- If the client's source system *can* emit those, they must be stripped or hashed **before** reaching the BigQuery feeds. We will not accept a feed and post-strip.
- `rpc_estimator_staging` is readable by `scoring-api-staging@msm-rpc.iam.gserviceaccount.com` and the named CI deployer; client-side reads of staging require explicit grant.
- A separate (more restricted) `rpc_estimator_prod` dataset will be created at Phase 3 with the same schema; the client identifies which client-side identities should have read access there.

## 5. Idempotency, corrections, and reversals

- **Clicks**: `click_id` is the primary key. Re-emits with the same `click_id` are dropped (last-write-wins on a 24-hour window). The client must not mutate features after first emit.
- **Ledger reversals** (refunds, chargebacks): emit a *new row* with the same `click_id` and `order_id` but **negative** `revenue`. We sum on read; we do not delete. `revenue_ts` is the reversal timestamp, not the original.
- Schema changes are versioned: any breaking change requires a new dataset (`rpc_estimator_staging_v2`) and a written migration plan. We do not silently add columns to live tables.

## 6. Data quality SLAs

We treat the following as *contract-breaking* and will alert the client on first breach:

| Rule                                                              | Threshold (rolling 24h) |
|-------------------------------------------------------------------|-------------------------|
| `cerberus_score` outside `[0, 1]`                                 | > 0.1% of rows          |
| `geo` outside ISO-3166-1 alpha-2                                  | > 1% of rows            |
| `revenue` < 0 not explained by a refund row                       | any                     |
| `clicks` row with no value in a REQUIRED column                   | any                     |
| `sales_ledger.click_id` with no matching `clicks.click_id`        | > 1% of rows            |

These are also the boundary conditions that the §5 anomaly window enforces at runtime — too many out-of-spec inputs will trip the breaker and fall back to tCPA.

## 7. What changes in the model when this lands

- `synthetic_clicks` and `sales_ledger_synthetic` stay; they're the test fixture for `ops/e2e/`.
- `rpc_training_rows` is rebuilt against the real `clicks` and `sales_ledger`.
- `ml-pipeline-train` re-runs and registers `rpc-estimator@2`. ADR 0002 — model upload now attaches the `explanationSpec` so `/v1/explain` returns real attributions.
- Drift monitors (Phase 2.4) compute PSI between the new training distribution and live inputs, and residuals against the ledger. Baseline distribution snapshot is taken on the first successful train.

## 8. Sign-off

| Role                          | Name | Date |
|-------------------------------|------|------|
| Client data owner             |      |      |
| Client engineering lead       |      |      |
| msm scoring-platform owner    |      |      |

Once signed, this file is the authoritative reference; later changes go via PR with sign-off from the same three roles.
