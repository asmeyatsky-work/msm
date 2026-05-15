-- predictions_vs_revenue view — joins logged predictions to realized revenue.
-- Consumed by the reconciliation service and by the dashboard.
--
-- ADR 0003 (sum-of-rewards): the label for a click is the sum of all
-- ledger rows for that click_id inside the reconciliation window —
-- charge-backs included (signed revenue). One row per click in this view.
--
-- The reconciliation window is configurable per environment via the
-- `${window_days}` placeholder, substituted at apply time:
--   * generic / e-commerce default: 30
--   * Credit Cards (ADR 0003): 90
-- See `infra/terraform/envs/*.tfvars` (`reconciliation_window_days`).

CREATE OR REPLACE VIEW `${project}.${dataset}.predictions_vs_revenue` AS
WITH pred AS (
  SELECT
    click_id,
    correlation_id,
    predicted_rpc,
    source,
    model_version,
    TIMESTAMP_MILLIS(ts_ms) AS predicted_at,
    ts_ms AS predicted_at_ms
  FROM `${project}.${dataset}.rpc_predictions`
),
rev AS (
  SELECT
    click_id,
    SUM(revenue) AS realized_rpc,
    MIN(TIMESTAMP_MILLIS(ts_ms)) AS first_revenue_at
  FROM `${project}.${dataset}.sales_ledger`
  GROUP BY click_id
)
SELECT
  p.click_id,
  p.correlation_id,
  p.predicted_rpc,
  COALESCE(r.realized_rpc, 0.0) AS realized_rpc,
  p.source,
  p.model_version,
  p.predicted_at_ms + (${window_days} * 24 * 60 * 60 * 1000) AS window_ends_at_ms,
  r.first_revenue_at
FROM pred p
LEFT JOIN rev r USING (click_id);
