#!/usr/bin/env bash
# Phase 1.5 staging load profile. Drives /v1/score and /v1/explain against the
# live staging Cloud Run service. The result JSON files land under ops/perf/
# and feed Phase 3.3 prod min-instances / concurrency sizing.
#
# Cost note: each request calls real Vertex AI and writes Pub/Sub. Stay below
# DURATION=60s / CONCURRENCY=20 unless coordinating with team — the staging
# endpoint is min=1 and will autoscale under sustained pressure.
#
# Requires: oha (cargo install oha), gcloud auth (for ID token), jq.
# Usage:  ops/perf/staging-load.sh [score|explain]  (default: both)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
URL="${SCORING_API_URL:-https://scoring-api-staging-ifcjcfl7xa-nw.a.run.app}"
DURATION="${DURATION:-30s}"
CONCURRENCY="${CONCURRENCY:-10}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

PAYLOAD='{"click_id":"perf-1","correlation_id":"perf","device":"mobile","geo":"US","hour_of_day":10,"query_intent":"x","ad_creative_id":"a","cerberus_score":0.5,"rpc_7d":1.0,"rpc_14d":1.0,"rpc_30d":1.0,"is_payday_week":false,"auction_pressure":0.5,"landing_path":"/","visits_prev_30d":0}'

mode="${1:-both}"

run_one() {
  local path="$1"
  local out="$ROOT/ops/perf/${TS}_${path//\//_}.json"
  echo ">>> ${DURATION} @ c=${CONCURRENCY} → ${URL}${path}"
  oha --no-tui --output-format json -z "$DURATION" -c "$CONCURRENCY" \
    -m POST -H "content-type: application/json" -d "$PAYLOAD" \
    "${URL}${path}" > "$out"
  jq '{
    rps: .rps,
    p50_ms: (.latencyPercentiles.p50 * 1000 | floor),
    p95_ms: (.latencyPercentiles.p95 * 1000 | floor),
    p99_ms: (.latencyPercentiles.p99 * 1000 | floor),
    success: .successRate,
    statusCodeDistribution: .statusCodeDistribution
  }' "$out"
}

case "$mode" in
  score)   run_one /v1/score ;;
  explain) run_one /v1/explain ;;
  both)    run_one /v1/score; run_one /v1/explain ;;
  *) echo "usage: $0 [score|explain|both]"; exit 2 ;;
esac
