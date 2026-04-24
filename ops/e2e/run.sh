#!/usr/bin/env bash
# E2E smoke: bring up scoring-api + fake Vertex in docker-compose, probe both
# /v1/score and /v1/explain, assert shape.
set -euo pipefail

cd "$(dirname "$0")"
trap 'docker compose logs --no-color scoring-api fake-vertex reconciliation || true; docker compose down -v --remove-orphans || true' EXIT

docker compose up -d --build

# Poll scoring-api from the host (distroless has no curl, so docker healthcheck
# can't run). Up to 60s for cold-start.
ready=0
for _ in $(seq 1 120); do
  if curl -fsS http://localhost:8080/healthz >/dev/null 2>&1; then ready=1; break; fi
  sleep 0.5
done
if [ "$ready" -ne 1 ]; then
  echo "::group::scoring-api logs"
  docker compose logs --no-color scoring-api
  echo "::endgroup::"
  exit 1
fi

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

# Reconciliation service: poll until FastAPI is up, then fetch a wide window.
ready=0
for _ in $(seq 1 120); do
  if curl -fsS http://localhost:8081/healthz >/dev/null 2>&1; then ready=1; break; fi
  sleep 0.5
done
if [ "$ready" -ne 1 ]; then
  echo "::error::reconciliation failed to start" >&2
  docker compose logs --no-color reconciliation
  exit 1
fi

REC=$(curl -fsS "http://localhost:8081/reconciliation?start=0&end=9999999999")
echo "$REC"
echo "$REC" | python3 -c 'import sys,json; d=json.load(sys.stdin); assert len(d)==2, d; ids=sorted(r["click_id"] for r in d); assert ids==["e2e-rec-1","e2e-rec-2"], ids'

echo "e2e: ok"
