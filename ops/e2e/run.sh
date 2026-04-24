#!/usr/bin/env bash
# E2E smoke: bring up scoring-api + fake Vertex in docker-compose, probe both
# /v1/score and /v1/explain, assert shape.
set -euo pipefail

cd "$(dirname "$0")"
trap 'docker compose down -v --remove-orphans || true' EXIT

docker compose up -d --build --wait

# Score path.
RESP=$(curl -fsS -X POST http://localhost:8080/v1/score \
  -H "content-type: application/json" \
  -d '{
    "click_id":"e2e-1","correlation_id":"e2e","device":"mobile","geo":"US",
    "hour_of_day":10,"query_intent":"commercial","ad_creative_id":"ad-e2e",
    "cerberus_score":0.5,"rpc_7d":1.0,"rpc_14d":1.0,"rpc_30d":1.0,
    "is_payday_week":false,"auction_pressure":0.5,
    "landing_path":"/","visits_prev_30d":0
  }')
echo "$RESP"
echo "$RESP" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d["predicted_rpc"]==2.5, d; assert d["source"]=="Model", d'

# Explain path.
EXP=$(curl -fsS -X POST http://localhost:8080/v1/explain \
  -H "content-type: application/json" \
  -d '{
    "click_id":"e2e-2","correlation_id":"e2e","device":"mobile","geo":"US",
    "hour_of_day":10,"query_intent":"commercial","ad_creative_id":"ad-e2e",
    "cerberus_score":0.5,"rpc_7d":1.0,"rpc_14d":1.0,"rpc_30d":1.0,
    "is_payday_week":false,"auction_pressure":0.5,
    "landing_path":"/","visits_prev_30d":0
  }')
echo "$EXP"
echo "$EXP" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert d["base_value"]==1.0, d; assert ("rpc_7d",0.3) in [tuple(x) for x in d["contributions"]], d'

echo "e2e: ok"
