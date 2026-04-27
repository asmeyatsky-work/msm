# Ingestion runbook (Phase 2.2)

Two flows. Schemas come from `docs/data-contract.md`.

## 1. Clicks — Pub/Sub → BigQuery (continuous)

Topic and BQ subscription provisioned in `infra/terraform/main.tf`:

- Topic: `projects/msm-rpc/topics/rpc-clicks-staging`
- Raw landing: `msm-rpc.rpc_estimator_staging.cm360_clicks_raw`
- Typed view: `msm-rpc.rpc_estimator_staging.cm360_clicks` (the one Dataform / training reads)

The client publishes one message per click. Message body is JSON matching the data contract:

```json
{
  "click_id": "abc-123",
  "click_ts": "2026-04-27T12:34:56Z",
  "device": "mobile",
  "geo": "GB",
  "hour_of_day": 12,
  "query_intent": "commercial",
  "ad_creative_id": "ad-042",
  "cerberus_score": 0.81,
  "rpc_7d": 1.23,
  "rpc_14d": 1.31,
  "rpc_30d": 1.18,
  "is_payday_week": false,
  "auction_pressure": 0.45,
  "landing_path": "/landing/007",
  "visits_prev_30d": 2
}
```

Smoke test from a workstation with publish access:

```bash
gcloud pubsub topics publish rpc-clicks-staging \
  --project=msm-rpc \
  --message='{"click_id":"smoke-1","click_ts":"2026-04-27T00:00:00Z","device":"mobile","geo":"GB","hour_of_day":0,"query_intent":"commercial","ad_creative_id":"ad-000","cerberus_score":0.5,"rpc_7d":1,"rpc_14d":1,"rpc_30d":1,"is_payday_week":false,"auction_pressure":0.5,"landing_path":"/","visits_prev_30d":0}'

# Within ~30s:
bq query --use_legacy_sql=false --project_id=msm-rpc \
  'SELECT * FROM `msm-rpc.rpc_estimator_staging.cm360_clicks` WHERE click_id="smoke-1"'
```

Grant the client's publishing identity `roles/pubsub.publisher` on the topic — that grant is **out of `wif.tf`** today; add when the client identity is named.

## 2. Sales ledger — scheduled query MERGE (hourly batch)

The client exposes a daily-or-better-refreshed table (e.g. `client-prj.warehouse.daily_revenue`); we run an hourly BQ scheduled query that merges deltas into `rpc_estimator_staging.sales_ledger`.

Template (replace `<source>` with the client's table — finalised at sign-off of `docs/data-contract.md`):

```sql
MERGE INTO `msm-rpc.rpc_estimator_staging.sales_ledger` T
USING (
  SELECT
    click_id,
    revenue,
    revenue_ts,
    order_id,
    UNIX_MILLIS(revenue_ts) AS ts_ms
  FROM `<source>`
  WHERE revenue_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 6 HOUR)
) S
ON T.click_id = S.click_id
   AND T.order_id IS NOT DISTINCT FROM S.order_id
   AND T.revenue_ts = S.revenue_ts
WHEN NOT MATCHED THEN
  INSERT (click_id, revenue, revenue_ts, order_id, ts_ms)
  VALUES (S.click_id, S.revenue, S.revenue_ts, S.order_id, S.ts_ms)
```

Refunds/chargebacks are *new rows* with negative revenue (data contract §5), so `MERGE` matches on the (`click_id`, `order_id`, `revenue_ts`) triple — a reversal will not match an original row and will append.

Create via Data Transfer Service (one-shot):

```bash
bq mk --transfer_config \
  --project_id=msm-rpc \
  --target_dataset=rpc_estimator_staging \
  --display_name='sales_ledger hourly merge' \
  --data_source=scheduled_query \
  --params='{"query":"<the SQL above>","write_disposition":"WRITE_APPEND"}' \
  --schedule='every 1 hours'
```

The transfer-config service account needs `roles/bigquery.dataEditor` on `rpc_estimator_staging` and `roles/bigquery.dataViewer` on the client's source dataset; document and add to `wif.tf` when the source is identified.

## 3. Verification

Once both feeds are flowing:

1. Row counts come up in `cm360_clicks` and `sales_ledger` within their freshness floors (data contract §3).
2. `dataform run` rebuilds `rpc_training_rows` and `rpc_estimator/click_revenue` against real data.
3. Re-run `ops/deploy_real_model.py` to register `rpc-estimator@2` (with `explanationSpec` per ADR 0002).
4. Drift monitors (`dataform/definitions/monitoring/`) start populating `psi_daily` and `residuals_daily`.
