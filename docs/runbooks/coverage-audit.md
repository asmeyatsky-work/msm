# Runbook — Coverage audit

**Symptom**
- Dashboard "Where we have full visibility" panel shows a red bar
  (coverage < 60%) for one or more slices, OR
- Alert: *coverage drop > 10% week-over-week on slice X*, OR
- Compliance / data owner asks "how much of our scored traffic is settling
  inside the 90-day window?"

PRD V2 §4.3 (`/coverage`), §4.5 (dashboard panel), §11 (the systematic-
vs-random missingness decision point in week 2).

## What "coverage" means

For every click we score, did a positive-revenue row land in the sales
ledger inside the **90-day** reconciliation window? Coverage is the
fraction of scored clicks that did. The view is `coverage_audit` (see
`dataform/definitions/monitoring/coverage_audit.sqlx`); it slices by
`product_type`, `device`, `geo`, `query_intent`, and day-of-week.

Coverage gaps come in two flavours:

- **Random** — every slice drops by roughly the same amount. Cause is
  typically ingestion lag, a CM360 export hiccup, or a Pub/Sub topic
  backlog. The model trains fine on the visible majority.
- **Systematic** — one slice is dramatically worse than the others
  (e.g. mobile coverage 35% while desktop is 85%). The model is now
  trained on a biased sample of the population it scores; predictions
  on the under-covered slice are unreliable. **This blocks promotion**
  of a new model version per PRD V2 §11.

## 1. Confirm

```bash
ENV=staging  # or client-cc
BQ_DATASET=rpc_estimator_${ENV}

bq query --use_legacy_sql=false --project_id=msm-rpc <<SQL
SELECT slice_dim, slice_value, clicks, covered_clicks,
       ROUND(coverage_rate * 100, 1) AS coverage_pct
FROM \`msm-rpc.${BQ_DATASET}.coverage_audit\`
ORDER BY coverage_rate ASC
LIMIT 20
SQL
```

The lowest-coverage rows are the candidates. Compare against last week:

```bash
bq query --use_legacy_sql=false --project_id=msm-rpc <<SQL
SELECT
  slice_dim, slice_value,
  ROUND(coverage_rate * 100, 1) AS today_pct,
  -- 7d-ago snapshot — if you have a snapshot table; if not, skip this query.
  NULL AS week_ago_pct
FROM \`msm-rpc.${BQ_DATASET}.coverage_audit\`
WHERE coverage_rate < 0.60
ORDER BY coverage_rate ASC
SQL
```

## 2. Triage — random or systematic?

Look at the spread across slices for the same dimension. If `product_type`
spans 55% → 60% → 62% → 58% → 61% → 57% → 59% it is random / uniform; if
it spans 78% / 79% / 35% / 80% / 77% / 81% / 75% the **35%** is
systematic.

For the **systematic** case, also check the day-of-week slice — a single
bad day usually points at an ingestion incident rather than a real
population bias.

## 3. Fix — random

The platform is doing its job; the data is in flight. Verify ingestion
freshness:

```bash
# Pub/Sub backlog on the sales-ledger topic, if used:
gcloud pubsub subscriptions list --filter="topic:rpc-ledger-${ENV}" \
  --format="table(name,messageRetentionDuration,ackDeadlineSeconds)"

# When did the last ledger row land?
bq query --use_legacy_sql=false --project_id=msm-rpc <<SQL
SELECT MAX(revenue_ts) AS last_revenue_ts,
       TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(revenue_ts), MINUTE) AS minutes_behind
FROM \`msm-rpc.${BQ_DATASET}.sales_ledger\`
SQL
```

If ingestion is healthy and coverage stabilises a week later, no action.
If freshness lags > 6 hours, page the data team and link this runbook.

## 4. Fix — systematic

This is a **release gate** issue per PRD V2 §11.

1. Capture the slice and the gap in an incident note.
2. Hand the slice + click-IDs to the client data team for backfill.
3. Until backfill lands, hold any canary promotion:
   - `client-cc` canary stays at its current traffic split.
   - A new model version may still register against the Vertex
     endpoint, but **does not** advance past 10% traffic until coverage
     on the affected slice is back above 70%.
4. If the gap exceeds 30 days, escalate per the data-contract sign-off
   chain in `docs/data-contract-credit-cards.md §8`.

## 5. Verify recovery

Re-run the query in step 1. Coverage should be moving back toward the
overall average within a week of backfill. Close the runbook when the
red bar is gone from the dashboard panel for two consecutive working
days.

## Related

- `coverage_audit.sqlx` — the materialising view.
- `coverage_drops_weekly.sqlx` — W-o-W breach rows; what the *coverage drop*
  alert pages on.
- `drift_breaches_weekly.sqlx` — companion view for per-segment residual
  MAE drift breaches. Look here when a drift alert lands.
- `ops/breach_emitter.py` — daily script that turns breach rows into log
  lines counted by the Cloud Monitoring metrics.
- `predictions_vs_revenue` — the joined view that drives the residuals.
- `docs/data-contract-credit-cards.md §3` — sales-ledger join key.
- `docs/PRD-v2-credit-cards.md §11` — the systematic-missingness risk.
