-- Synthetic bootstrap data for staging. Run via:
--   bq query --use_legacy_sql=false --project_id=msm-rpc < ops/seed_synthetic_data.sql
--
-- Creates 5,000 synthetic (click, realized_revenue) rows so the XGBoost
-- model has something to fit on. Distribution is deliberately non-trivial
-- (cerberus_score and rpc_7d strongly predict revenue) so a tree model can
-- discover real structure.

-- 1. Clicks with features (we synthesize CM360 clicks directly in the ledger
--    for brevity — click_id doubles as order_id).
CREATE OR REPLACE TABLE `msm-rpc.rpc_estimator_staging.synthetic_clicks` AS
WITH rand AS (
  SELECT
    FORMAT('click-%05d', n) AS click_id,
    TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL CAST(RAND() * 86400 * 30 AS INT64) SECOND) AS click_ts,
    IF(RAND() < 0.55, 'mobile', IF(RAND() < 0.7, 'desktop', 'tablet')) AS device,
    IF(RAND() < 0.6, 'GB', IF(RAND() < 0.75, 'US', IF(RAND() < 0.85, 'DE', 'FR'))) AS geo,
    CAST(RAND() * 24 AS INT64) AS hour_of_day,
    IF(RAND() < 0.4, 'commercial', IF(RAND() < 0.75, 'informational', 'navigational')) AS query_intent,
    FORMAT('ad-%03d', CAST(RAND() * 50 AS INT64)) AS ad_creative_id,
    -- cerberus_score is a fraud/quality signal — high values → more revenue
    POW(RAND(), 2) AS cerberus_score,
    -- Rolling RPCs also correlate with revenue
    RAND() * 5 AS rpc_7d,
    RAND() * 5 AS rpc_14d,
    RAND() * 5 AS rpc_30d,
    RAND() < 0.25 AS is_payday_week,
    RAND() AS auction_pressure,
    '/landing/' || FORMAT('%03d', CAST(RAND() * 20 AS INT64)) AS landing_path,
    CAST(RAND() * 10 AS INT64) AS visits_prev_30d
  FROM UNNEST(GENERATE_ARRAY(1, 5000)) AS n
)
SELECT * FROM rand;

-- 2. Sales ledger — realized revenue drawn from a function of features,
--    with noise. 60% of clicks convert (have a row); rest don't.
CREATE OR REPLACE TABLE `msm-rpc.rpc_estimator_staging.sales_ledger_synthetic` AS
SELECT
  click_id,
  -- Revenue = base + cerberus × weight + rpc_7d × weight + geo bonus + noise
  GREATEST(
    0.0,
    0.5
    + cerberus_score * 10.0
    + rpc_7d * 2.0
    + IF(geo = 'GB', 2.0, IF(geo = 'US', 1.5, 0.5))
    + (RAND() - 0.5) * 3.0
  ) AS revenue,
  TIMESTAMP_ADD(click_ts, INTERVAL CAST(RAND() * 86400 * 7 AS INT64) SECOND) AS revenue_ts,
  click_id AS order_id,
  UNIX_MILLIS(TIMESTAMP_ADD(click_ts, INTERVAL CAST(RAND() * 86400 * 7 AS INT64) SECOND)) AS ts_ms
FROM `msm-rpc.rpc_estimator_staging.synthetic_clicks`
WHERE RAND() < 0.60;

-- 3. Copy into the real sales_ledger table (insert, not replace, so prod
--    inflows don't get clobbered if this is re-run later).
INSERT INTO `msm-rpc.rpc_estimator_staging.sales_ledger` (click_id, revenue, revenue_ts, order_id, ts_ms)
SELECT click_id, revenue, revenue_ts, order_id, ts_ms
FROM `msm-rpc.rpc_estimator_staging.sales_ledger_synthetic`;

-- 4. Training view — join clicks ↔ revenue, align with msm_ml.domain.FeatureVector.
CREATE OR REPLACE VIEW `msm-rpc.rpc_estimator_staging.rpc_training_rows` AS
SELECT
  c.click_id,
  UNIX_MILLIS(c.click_ts) AS click_ts_ms,
  c.device,
  c.geo,
  c.hour_of_day,
  c.cerberus_score,
  c.rpc_7d,
  c.rpc_14d,
  c.rpc_30d,
  c.is_payday_week,
  c.auction_pressure,
  c.visits_prev_30d,
  COALESCE(s.revenue, 0.0) AS target_revenue
FROM `msm-rpc.rpc_estimator_staging.synthetic_clicks` c
LEFT JOIN `msm-rpc.rpc_estimator_staging.sales_ledger_synthetic` s
  ON s.click_id = c.click_id;
