# Rollback plan (Phase 3.6)

Every prod deploy is rollback-ready. This document specifies *what* you can roll back, *how*, and *what to verify* afterwards. The dry-run script `ops/rollback/dry-run.sh` validates the preconditions hold before you need them.

## 1. Layers of rollback (cheapest first)

| Layer                   | Mechanism                                            | Time-to-rollback | Reversible? |
|-------------------------|------------------------------------------------------|------------------|-------------|
| Vertex traffic split    | `gcloud ai endpoints traffic-split set` to prior id  | < 1 min          | Yes (re-split)        |
| Cloud Run revision pin  | `gcloud run services update-traffic --to-revisions`  | < 1 min          | Yes (re-pin)          |
| Runtime kill switch     | Bump `rpc-runtime-config-${env}` secret with `kill=true` | < 30 s          | Yes (next bump)       |
| Secret rollback         | Disable current version, re-enable prior             | < 1 min          | Yes                   |
| BQ schema rollback      | Read from `_v2` dataset; old dataset untouched 7d    | Minutes          | Yes within 7d window  |
| Tag-revert deploy       | `git revert <sha> && git push origin v0.x.y+1`       | ~10 min          | Yes (forward fix)     |

Pick the cheapest layer that resolves the symptom — there's no merit in re-deploying when a traffic split would do.

## 2. Decision tree

```
incident detected
  │
  ├── "predictions look wrong" / drift / residuals diverge
  │     → docs/runbooks/model-rollback.md (Vertex traffic split)
  │
  ├── "scoring-api 5xx surge after a deploy"
  │     → Cloud Run revision pin (this doc §3)
  │
  ├── "we need to stop scoring NOW (compliance / data leak / runaway cost)"
  │     → Kill switch (this doc §4) — no deploy required, ~30 s
  │
  ├── "secret got leaked"
  │     → docs/runbooks/secret-rotation.md
  │
  └── "schema migration broke a downstream"
        → BQ dataset revert (this doc §5 + bq-schema-migration.md §2)
```

## 3. Cloud Run revision pin

```bash
PROJECT=msm-rpc; ENV=prod; REGION=europe-west2
SERVICE=scoring-api-$ENV

# List revisions (most recent first)
gcloud run revisions list --service=$SERVICE \
  --project=$PROJECT --region=$REGION \
  --format='table(metadata.name,status.conditions[0].lastTransitionTime)' --limit=5

# Pin all traffic to the prior revision
PREV=$(gcloud run revisions list --service=$SERVICE \
  --project=$PROJECT --region=$REGION \
  --format='value(metadata.name)' --limit=2 | tail -n1)

gcloud run services update-traffic $SERVICE \
  --project=$PROJECT --region=$REGION \
  --to-revisions=$PREV=100
```

Any subsequent CD deploy will create a new revision *but receive 0% of traffic* until you re-split. To resume normal forward-deploy: `gcloud run services update-traffic --to-latest`.

## 4. Kill switch

The fastest "stop scoring" lever. Sets `kill=true` in the runtime config secret; scoring-api re-reads within ~15 s and falls every request through to tCPA fallback.

```bash
ENV=prod
gcloud secrets versions add rpc-runtime-config-$ENV --project=msm-rpc --data-file=- <<'EOF'
{"kill":true,"bounds_min":0.01,"bounds_max":500.0,"canary_bp":10000}
EOF
```

Resume by repeating with `"kill":false`.

## 5. BQ dataset revert (post schema migration)

Within the 7-day parallel-run window of a breaking schema change:

1. Flip readers' `BQ_DATASET` env back to the previous dataset (`rpc_estimator_${env}` instead of `_v2`).
2. Stop the second Pub/Sub→BQ subscription writing to `_v2`.
3. Triage the migration in a forward-fix; do not delete `_v2`.

After 7 days the old dataset is dropped — beyond that window, recovery is via BQ snapshot (`bq cp <table>@<unix_ts_ms>`).

## 6. Pre-flight: verify rollback is possible

Run before any non-trivial deploy:

```bash
ops/rollback/dry-run.sh prod
```

The script asserts:
- ≥ 2 `deployedModels` on the Vertex endpoint (so traffic split has somewhere to go).
- ≥ 2 Cloud Run revisions exist for `scoring-api-prod`.
- A non-killed runtime-config version exists.
- Latest BQ table snapshots are within 24h.

Exit non-zero ⇒ rollback path is broken; fix before deploying.

## 7. After any rollback

- Open `docs/incidents/YYYY-MM-DD.md` with: trigger, layer used, time-to-detect, time-to-restore, follow-up actions.
- File the forward-fix as a normal change; re-run pre-flight before the next deploy.
- Keep the rolled-back artefact in place for 24 h before releasing the bytes (gives time to extract diagnostic data).
