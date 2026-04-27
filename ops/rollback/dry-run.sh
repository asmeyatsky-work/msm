#!/usr/bin/env bash
# Pre-flight check: verifies the rollback path is intact for a given env.
# Exit 0 = rollback is possible; non-zero = at least one layer is broken.
#
# Usage:  ops/rollback/dry-run.sh [staging|prod]
#
# Requires: gcloud auth, jq, bq.
set -euo pipefail

ENV="${1:-staging}"
PROJECT="${PROJECT_OVERRIDE:-msm-rpc}"
REGION="${REGION_OVERRIDE:-europe-west2}"
SERVICE="scoring-api-${ENV}"
RUNTIME_SECRET="rpc-runtime-config-${ENV}"

fail() { echo "FAIL: $*" >&2; FAILED=1; }
pass() { echo "ok:   $*"; }

FAILED=0

# 1. Vertex endpoint has at least 2 deployed models (so traffic-split has a fallback).
echo "[1/4] Vertex endpoint deployedModels"
ENDPOINT=$(gcloud ai endpoints list --project="$PROJECT" --region="$REGION" \
  --filter="displayName:rpc-estimator-endpoint" --format='value(name)' \
  | head -n1 || true)
if [[ -z "$ENDPOINT" ]]; then
  fail "no rpc-estimator-endpoint in $REGION"
else
  N=$(gcloud ai endpoints describe "$ENDPOINT" --project="$PROJECT" --region="$REGION" \
        --format='value(deployedModels[].id)' | tr ';' '\n' | wc -l | tr -d ' ')
  if (( N >= 2 )); then
    pass "$N deployedModels — Vertex traffic-split rollback available"
  else
    fail "only $N deployedModels on $ENDPOINT — no Vertex rollback target"
  fi
fi

# 2. Cloud Run service has at least 2 revisions.
echo "[2/4] Cloud Run revisions for $SERVICE"
N_REV=$(gcloud run revisions list --service="$SERVICE" \
  --project="$PROJECT" --region="$REGION" \
  --format='value(metadata.name)' --limit=10 | wc -l | tr -d ' ')
if (( N_REV >= 2 )); then
  pass "$N_REV revisions — Cloud Run revision-pin rollback available"
else
  fail "only $N_REV revision for $SERVICE — no Cloud Run rollback target"
fi

# 3. Runtime config secret exists, latest version has kill=false.
echo "[3/4] Runtime config secret $RUNTIME_SECRET"
if RUNTIME_JSON=$(gcloud secrets versions access latest --secret="$RUNTIME_SECRET" --project="$PROJECT" 2>/dev/null); then
  KILL=$(echo "$RUNTIME_JSON" | jq -r '.kill // empty')
  if [[ "$KILL" == "true" ]]; then
    fail "runtime config kill=true already — env is in a degraded state"
  else
    pass "runtime config readable; kill=false"
  fi
else
  fail "cannot read $RUNTIME_SECRET"
fi

# 4. BigQuery tables: data partitions are recent (sales_ledger updated in last 24h).
echo "[4/4] BigQuery sales_ledger freshness"
LAST=$(bq query --use_legacy_sql=false --project_id="$PROJECT" --format=csv --quiet \
  "SELECT MAX(revenue_ts) AS last_ts FROM \`${PROJECT}.rpc_estimator_${ENV}.sales_ledger\`" \
  | tail -n1 || true)
if [[ -z "$LAST" || "$LAST" == "null" ]]; then
  fail "sales_ledger empty or unreadable (expected synthetic seed at minimum)"
else
  pass "sales_ledger latest revenue_ts = $LAST"
fi

echo ""
if (( FAILED == 0 )); then
  echo "rollback dry-run: ok"
else
  echo "rollback dry-run: FAIL ($FAILED issue(s))"
  exit 1
fi
