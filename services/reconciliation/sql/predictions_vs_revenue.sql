-- Materialized view joining logged predictions with realized revenue.
-- Consumed by the reconciliation service and by Looker (PRD §2.2).
-- The conversion window is configurable (PRD §3.2); defaults to 30d.

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
  p.predicted_at_ms + (30 * 24 * 60 * 60 * 1000) AS window_ends_at_ms,
  r.first_revenue_at
FROM pred p
LEFT JOIN rev r USING (click_id);
