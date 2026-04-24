#!/usr/bin/env bash
# Load test driving /v1/score against the real Rust binary with a fake Vertex.
# Fails CI if p99 exceeds the PRD §2.2 budget (100ms).
#
# Requires: oha (cargo install oha), python3, cargo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUDGET_P99_MS="${BUDGET_P99_MS:-100}"
DURATION="${DURATION:-10s}"
CONCURRENCY="${CONCURRENCY:-50}"

# 1. Start a tiny fake Vertex that returns a constant prediction with ~5ms latency.
python3 -m http.server 0 --bind 127.0.0.1 &  # placeholder to find a port
kill $! 2>/dev/null || true
VERTEX_PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")

python3 - "$VERTEX_PORT" <<'PY' &
import json, sys, time
from http.server import BaseHTTPRequestHandler, HTTPServer
port = int(sys.argv[1])
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if "/token" in self.path:
            body = json.dumps({"access_token":"fake","expires_in":3600}).encode()
            self.send_response(200); self.send_header("content-type","application/json")
            self.send_header("content-length", str(len(body))); self.end_headers()
            self.wfile.write(body); return
        self.send_response(404); self.end_headers()
    def do_POST(self):
        n = int(self.headers.get("content-length","0"))
        self.rfile.read(n)
        body = json.dumps({"predictions":[2.5]}).encode()
        self.send_response(200); self.send_header("content-type","application/json")
        self.send_header("content-length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self,*a,**k): pass
HTTPServer(("127.0.0.1", port), H).serve_forever()
PY
VERTEX_PID=$!
trap 'kill $VERTEX_PID 2>/dev/null || true; kill $API_PID 2>/dev/null || true' EXIT

sleep 0.5

# 2. Start scoring-api against the fake.
API_PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()")
export GCP_METADATA_TOKEN_URL="http://127.0.0.1:${VERTEX_PORT}/token"
export VERTEX_ENDPOINT_URL="http://127.0.0.1:${VERTEX_PORT}/predict"
export VERTEX_EXPLAIN_URL="http://127.0.0.1:${VERTEX_PORT}/explain"
export MODEL_VERSION="load"
export GCP_PROJECT="load"
export BQ_DATASET="load"
export BQ_LEDGER_TABLE="load"
export PREDICTIONS_TOPIC="rpc-predictions-load"
export LISTEN_ADDR="127.0.0.1:${API_PORT}"
export RPC_MIN="0.01" RPC_MAX="500"

(cd "$ROOT/services/scoring-api" && cargo run --release -q --bin scoring-api) &
API_PID=$!

# Wait until /healthz responds.
for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${API_PORT}/healthz" >/dev/null 2>&1; then break; fi
  sleep 0.5
done

# 3. Drive load with oha (Rust-native; structured JSON output).
PAYLOAD='{"click_id":"l-1","correlation_id":"l","device":"mobile","geo":"US","hour_of_day":10,"query_intent":"x","ad_creative_id":"a","cerberus_score":0.5,"rpc_7d":1.0,"rpc_14d":1.0,"rpc_30d":1.0,"is_payday_week":false,"auction_pressure":0.5,"landing_path":"/","visits_prev_30d":0}'

REPORT=$(oha --json -z "$DURATION" -c "$CONCURRENCY" \
  -m POST -H "content-type: application/json" -d "$PAYLOAD" \
  "http://127.0.0.1:${API_PORT}/v1/score")

echo "$REPORT" | python3 -m json.tool

P99_S=$(echo "$REPORT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["latencyPercentiles"]["p99"])')
P99_MS=$(python3 -c "print(int(float('${P99_S}') * 1000))")

echo "p99 = ${P99_MS}ms (budget ${BUDGET_P99_MS}ms)"
if [ "$P99_MS" -gt "$BUDGET_P99_MS" ]; then
  echo "::error::p99 exceeds budget" >&2
  exit 1
fi
echo "load: ok"
