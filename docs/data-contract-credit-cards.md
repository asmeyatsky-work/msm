# Data Contract — Credit Cards Predictive Bidding MVP

**Status:** Draft for client sign-off
**Owner (us):** scoring-platform team
**Owner (client):** [name TBD — data]
**Owner (client compliance):** [name TBD — required to countersign §6 & §8]
**Target:** Phase 1 ingestion live within 5 business days of sign-off.

This is the Credit-Cards-specific addendum to `docs/data-contract.md`.
Anything not overridden here defaults to the generic contract.

---

## 1. Why this contract exists

The platform is built and demonstrated against synthetic data. To
move to a Credit Cards MVP we need:

- A real **click feed** from the client's PPC pipeline (CM360 / SA360
  events).
- A real **sales-ledger feed** covering all monetisable Credit Cards
  events (application started, submitted, approved, activated +
  first eligible spend, charge-backs).
- A join key that links a click to one or more ledger events.

Once signed, every downstream artefact (ingestion, training, drift
monitors, prod cutover, retrain trigger) is built against the schemas
below.

## 2. Coverage trajectory

The client has flagged that today only ~50% of Credit Cards sales are
visible to the PPC system, rising to ~80% by **end of June 2026**.

We will:

- **Audit** the missing 50% along partner / channel / device / card
  product / attribution window in the first week after sign-off
  (`dataform/definitions/coverage_audit.sqlx`). Output goes to the
  dashboard's coverage panel and a short written report.
- **Train v1 on the visible 50%** as a learning environment, not a
  production bidding signal. Calibration is monitored on the visible
  slice only.
- **Retrain v2 on 80% data end of June**, traffic-split 10% → 100%
  over a couple of days using the existing Vertex AI canary machinery
  (`docs/runbooks/canary-deploy.md`).
- **Cut over to v2** end of July, decommission v1.

The audit decides whether v1 is honest "everywhere" or honest "only in
slices A and B". If the missingness is systematic we will either fix
the ingestion gap before training v1 or serve a deterministic fallback
in the unseen slices.

## 3. Click feed

Replaces the generic schema in `data-contract.md §2.1`. Credit-cards-
specific fields are flagged **CC**.

| Column                  | Type      | Mode | Notes |
|-------------------------|-----------|------|-------|
| `click_id`              | STRING    | REQ  | Stable, globally unique. Opaque to the bidder; **not** a hash of any customer attribute. |
| `correlation_id`        | STRING    | REQ  | Trace ID for joining to the bidder logs. |
| `click_ts`              | TIMESTAMP | REQ  | UTC. Partition column. |
| `device`                | STRING    | REQ  | `mobile` / `desktop` / `tablet`. |
| `geo`                   | STRING    | REQ  | ISO-3166-1 alpha-2. |
| `hour_of_day`           | INT64     | REQ  | 0–23, derived from `click_ts` in click's local TZ. |
| **`product_type`** (CC) | STRING    | REQ  | One of `cashback`, `travel`, `balance_transfer`, `premium`, `student`, `business`, `secured`. Other values rejected at ingest. |
| **`card_product_id`** (CC) | STRING | REQ  | Client's internal product SKU (e.g. `CC-CASHBACK-PLATINUM`). Stable. |
| **`query_intent`** (CC) | STRING    | REQ  | One of `compare`, `shop`, `apply`, `research`, `navigational`. Replaces the generic e-commerce taxonomy. |
| **`affinity_score`** (CC)| FLOAT64  | REQ  | `[0.0, 1.0]`. Client-side derived from the query terms; higher = closer match to the product. |
| `ad_creative_id`        | STRING    | REQ  | Stable creative ID (CM360 export). |
| **`prior_applicant`** (CC) | BOOL   | REQ  | Has the originating user-cookie applied for any client card in the last 90 days? **Cookie-level**, never customer-level. |
| **`income_band_bucket`** (CC, optional) | STRING | NULL | One of `low`, `mid`, `high` or NULL if unknown. Bucketed at source; raw values are never sent. |
| `auction_pressure`      | FLOAT64   | REQ  | `[0.0, 1.0]`. |
| **`rpc_14d`** (CC)      | FLOAT64   | REQ  | 14-day rolling realised RPC for this `product_type`. ≥ 0. |
| **`rpc_60d`** (CC)      | FLOAT64   | REQ  | 60-day rolling realised RPC for this `product_type`. Replaces `rpc_7d/rpc_30d` — the longer windows are more meaningful for Credit Cards. |
| `landing_path`          | STRING    | REQ  | Path only. No querystring. No customer identifiers. |
| `visits_prev_30d`       | INT64     | REQ  | Cookie-level visit count. ≥ 0. |

**Removed from the generic schema:** `cerberus_score`, `rpc_7d`,
`rpc_30d`, `is_payday_week`. These were e-commerce proxies that don't
map to Credit Cards bidder signals.

**Volume estimate needed from client:** clicks per day for each
`product_type`. Drives Vertex AI machine sizing.

## 4. Sales-ledger feed

Replaces the generic schema in `data-contract.md §2.2`.

Credit Cards monetises across **stages**; each stage is one row.
ADR 0003 (sum-of-rewards) governs how stages combine at training
time — the model sees `SUM(revenue) WHERE click_id = …` inside the
reconciliation window.

| Column            | Type      | Mode | Notes |
|-------------------|-----------|------|-------|
| `ledger_event_id` | STRING    | REQ  | Unique per row. |
| `click_id`        | STRING    | REQ  | Joins back to the click feed. |
| `event_ts`        | TIMESTAMP | REQ  | UTC. Partition column. |
| **`stage`** (CC)  | STRING    | REQ  | One of `application_started`, `application_submitted`, `approved`, `activated`, `first_spend`, `chargeback`. |
| `revenue`         | FLOAT64   | REQ  | Signed. Negative for charge-backs. |
| `currency`        | STRING    | REQ  | ISO-4217 (`GBP` default). Anything other than `GBP` is rejected by the ingest step until we sign off on FX handling. |
| `card_product_id` | STRING    | REQ  | Same SKU vocabulary as the click feed. |

**Volume estimate needed:** ledger events per day, per stage.

## 5. Reconciliation window

Generic platform uses 30 days. Credit Cards uses **90 days**, set in
`infra/terraform/envs/<client-env>.tfvars` as
`reconciliation_window_days = 90`. The longer window is justified by
the lag distribution in §4 (first-spend may not arrive for 30–60 days
after the click).

## 6. PII inventory

Maps directly to ADR 0004 (FCA compliance boundary).

| Field | Class | Lives where | Retention |
|---|---|---|---|
| `click_id`, `correlation_id`, `ledger_event_id` | opaque IDs, not PII | BigQuery `rpc_estimator_*` | 180 days; aggregates retained indefinitely |
| `device`, `geo`, `hour_of_day` | non-PII context | BigQuery | as above |
| `product_type`, `card_product_id`, `query_intent`, `affinity_score`, `prior_applicant`, `income_band_bucket` | non-PII product / cohort signal (bucketed at source) | BigQuery | as above |
| `ad_creative_id`, `landing_path` | non-PII creative metadata | BigQuery | as above |
| `stage`, `revenue`, `currency` | revenue facts; not linked to any customer in our system | BigQuery | as above |

**Not received, not stored:**
- Customer name, email, postal address, date of birth, NI number.
- Card number, account number, sort code.
- IP address, full user-agent, geolocation beyond `geo` (country).
- Credit-bureau scores, application decisions, APR offered, credit
  limit issued, term-sheet content.

Right-to-erasure on a click is supported by deleting the row from
`rpc_predictions_raw` and `cm360_clicks_raw` keyed on `click_id`;
because no PII is stored, full PII-erasure obligations under UK GDPR
are satisfied by deleting the originating client systems' records.

## 7. Refresh cadence

- **Click feed:** streaming via Pub/Sub topic
  `rpc-clicks-<client-env>` (target latency: < 2 min from click to BQ).
- **Sales-ledger feed:** batch via BigQuery scheduled query or
  Transfer Service (target: hourly refresh, max 24 h lag end-to-end).

## 8. Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Client — Data owner | _TBD_ | | |
| Client — Engineering lead | _TBD_ | | |
| Client — Compliance contact (countersigns §6 PII inventory) | _TBD_ | | |
| Searce — Platform lead | Allan Smeyatsky | | |

Once signed, this document is the source of truth for the Credit
Cards ingestion. Schema changes are made via PR against this file
with both parties re-signing.
