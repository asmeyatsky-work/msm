#!/usr/bin/env bash
# Post-deploy smoke: hit /healthz and /v1/score once. Fails loud on any
# non-2xx — the CD job uses this to halt promotion to prod.
set -euo pipefail

URL="${1:?scoring-api URL required}"

echo "smoke: healthz"
curl -fsS "${URL}/healthz" | grep -q ok

echo "smoke: score"
curl -fsS -X POST "${URL}/v1/score" \
  -H "content-type: application/json" \
  -d '{
    "click_id":"smoke-1","correlation_id":"smoke","device":"mobile","geo":"US",
    "hour_of_day":10,"query_intent":"commercial","ad_creative_id":"ad-smoke",
    "cerberus_score":0.5,"rpc_7d":1.0,"rpc_14d":1.0,"rpc_30d":1.0,
    "is_payday_week":false,"auction_pressure":0.5,
    "landing_path":"/","visits_prev_30d":0
  }' | grep -q '"predicted_rpc"'

echo "smoke: ok"
