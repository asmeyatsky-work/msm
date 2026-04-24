#!/usr/bin/env bash
# Post-deploy smoke: verify scoring-api is up. /v1/score needs a real
# Vertex endpoint + sales_ledger table to 200, so first deploy only
# asserts /health. Once a real model is registered, re-enable the
# /v1/score check with a known-good payload.
set -euo pipefail

URL="${1:?scoring-api URL required}"

echo "smoke: health"
curl -fsS "${URL}/health" | grep -q ok
echo "smoke: ok"
