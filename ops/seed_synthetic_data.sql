-- Synthetic bootstrap data for staging. Run via:
--   bq query --use_legacy_sql=false --project_id=msm-rpc < ops/seed_synthetic_data.sql
--
-- Creates 5,000 synthetic (click, realized_revenue) rows so the XGBoost
-- model has something to fit on. Distribution is deliberately non-trivial
-- (affinity_score and rpc_14d strongly predict revenue) so a tree model can
-- discover real structure. Schema: PRD V2 (Credit Cards) §7.

-- 1. Clicks with features (we synthesize CM360 clicks directly in the ledger
--    for brevity — click_id doubles as order_id).
CREATE OR REPLACE TABLE `msm-rpc.rpc_estimator_staging.synthetic_clicks` AS
WITH rand AS (
  SELECT
    FORMAT('click-%05d', n) AS click_id,
    GENERATE_UUID() AS correlation_id,
    TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL CAST(RAND() * 86400 * 30 AS INT64) SECOND) AS click_ts,
    'credit_cards' AS vertical_id,
    IF(RAND() < 0.55, 'mobile', IF(RAND() < 0.7, 'desktop', 'tablet')) AS device,
    IF(RAND() < 0.6, 'GB', IF(RAND() < 0.75, 'US', IF(RAND() < 0.85, 'DE', 'FR'))) AS geo,
    CAST(RAND() * 24 AS INT64) AS hour_of_day,
    CASE
      WHEN RAND() < 0.25 THEN 'cashback'
      WHEN RAND() < 0.45 THEN 'travel'
      WHEN RAND() < 0.60 THEN 'balance_transfer'
      WHEN RAND() < 0.75 THEN 'premium'
      WHEN RAND() < 0.85 THEN 'student'
      WHEN RAND() < 0.93 THEN 'business'
      ELSE 'secured'
    END AS product_type,
    FORMAT('card-%03d', CAST(RAND() * 30 AS INT64)) AS card_product_id,
    CASE
      WHEN RAND() < 0.25 THEN 'compare'
      WHEN RAND() < 0.50 THEN 'shop'
      WHEN RAND() < 0.70 THEN 'apply'
      WHEN RAND() < 0.90 THEN 'research'
      ELSE 'navigational'
    END AS query_intent,
    FORMAT('ad-%03d', CAST(RAND() * 50 AS INT64)) AS ad_creative_id,
    -- affinity_score: a CC-domain quality signal — high values → more revenue
    POW(RAND(), 2) AS affinity_score,
    RAND() < 0.20 AS prior_applicant,
    CASE
      WHEN RAND() < 0.40 THEN CAST(NULL AS STRING)
      WHEN RAND() < 0.60 THEN 'low'
      WHEN RAND() < 0.85 THEN 'mid'
      ELSE 'high'
    END AS income_band_bucket,
    -- Rolling RPCs also correlate with revenue
    RAND() * 5 AS rpc_14d,
    RAND() * 5 AS rpc_60d,
    RAND() AS auction_pressure,
    '/credit-cards/' || FORMAT('%03d', CAST(RAND() * 20 AS INT64)) AS landing_path,
    CAST(RAND() * 10 AS INT64) AS visits_prev_30d,
    -- Phoebe / GA4 behavioural features (PRD V2 §7.1). Distributions
    -- chosen so that high behavioural signal correlates with revenue
    -- in the sales-ledger generator — the model should pick this up
    -- as a real Phoebe lift.
    RAND() < 0.40 AS phoebe_calculator_used,
    CAST(RAND() * 8 AS INT64) AS phoebe_guides_read,
    CAST(RAND() * 12 AS INT64) AS phoebe_cards_compared,
    POW(RAND(), 0.7) * 600 AS phoebe_session_engagement_s,
    -- Phoebe join key. ~70% of synthetic clicks have a user_pseudo_id
    -- to simulate the GA4 cookie match-rate Phoebe expects in
    -- production.
    IF(RAND() < 0.70,
       FORMAT('upid-%05d', CAST(RAND() * 3500 AS INT64)),
       NULL) AS user_pseudo_id
  FROM UNNEST(GENERATE_ARRAY(1, 5000)) AS n
)
SELECT * FROM rand;

-- 2. Sales ledger — realized revenue drawn from a function of features,
--    with noise. 60% of clicks convert (have a row); rest don't.
CREATE OR REPLACE TABLE `msm-rpc.rpc_estimator_staging.sales_ledger_synthetic` AS
SELECT
  GENERATE_UUID() AS ledger_event_id,
  click_id,
  -- Revenue = base + affinity × weight + rpc_14d × weight + geo bonus +
  --           Phoebe signal × weight + noise. The Phoebe term models the
  --           strategy doc's "Bouncer with a Crystal Ball" — users who
  --           used a calculator and compared multiple cards convert at
  --           materially higher revenue than browsers.
  GREATEST(
    0.0,
    0.5
    + affinity_score * 10.0
    + rpc_14d * 2.0
    + IF(geo = 'GB', 2.0, IF(geo = 'US', 1.5, 0.5))
    + IF(phoebe_calculator_used, 3.0, 0.0)
    + phoebe_cards_compared * 0.25
    + (phoebe_session_engagement_s / 600.0) * 1.5
    + (RAND() - 0.5) * 3.0
  ) AS revenue,
  CAST(NULL AS FLOAT64) AS margin_rate, -- Soteria not yet wired
  TIMESTAMP_ADD(click_ts, INTERVAL CAST(RAND() * 86400 * 30 AS INT64) SECOND) AS revenue_ts,
  -- Multi-stage ledger (ADR 0003 sum-of-rewards); for the seed we emit one
  -- 'first_spend' row per converting click.
  'first_spend' AS stage,
  card_product_id,
  'GBP' AS currency,
  click_id AS order_id,
  UNIX_MILLIS(TIMESTAMP_ADD(click_ts, INTERVAL CAST(RAND() * 86400 * 30 AS INT64) SECOND)) AS ts_ms
FROM `msm-rpc.rpc_estimator_staging.synthetic_clicks`
WHERE RAND() < 0.60;

-- 3. Copy into the real sales_ledger table (insert, not replace, so prod
--    inflows don't get clobbered if this is re-run later).
INSERT INTO `msm-rpc.rpc_estimator_staging.sales_ledger`
  (ledger_event_id, click_id, revenue, margin_rate, revenue_ts, stage, card_product_id, currency, order_id, ts_ms)
SELECT ledger_event_id, click_id, revenue, margin_rate, revenue_ts, stage, card_product_id, currency, order_id, ts_ms
FROM `msm-rpc.rpc_estimator_staging.sales_ledger_synthetic`;

-- 4. Training view — join clicks ↔ revenue, align with msm_ml.domain.FeatureVector.
CREATE OR REPLACE VIEW `msm-rpc.rpc_estimator_staging.rpc_training_rows` AS
SELECT
  c.click_id,
  UNIX_MILLIS(c.click_ts) AS click_ts_ms,
  c.vertical_id,
  c.device,
  c.geo,
  c.hour_of_day,
  c.product_type,
  c.card_product_id,
  c.query_intent,
  c.affinity_score,
  c.prior_applicant,
  c.income_band_bucket,
  c.rpc_14d,
  c.rpc_60d,
  c.auction_pressure,
  c.visits_prev_30d,
  c.phoebe_calculator_used,
  c.phoebe_guides_read,
  c.phoebe_cards_compared,
  c.phoebe_session_engagement_s,
  COALESCE(s.revenue * COALESCE(s.margin_rate, 1.0), 0.0) AS target_revenue
FROM `msm-rpc.rpc_estimator_staging.synthetic_clicks` c
LEFT JOIN `msm-rpc.rpc_estimator_staging.sales_ledger_synthetic` s
  ON s.click_id = c.click_id;
