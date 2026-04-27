# Runbook — Roll back a Vertex model deploy

**Symptom**
- New `rpc-estimator@N` deploy is producing bad predictions (residuals in `dataform/.../residuals_daily` are 5× worse than the prior version, or PSI shows `major_shift` on multiple features, or `/v1/score` p95 latency doubled).

## 1. Confirm the prior version is healthy and reachable

```bash
PROJECT=msm-rpc
REGION=europe-west2
ENV=staging  # or prod
ENDPOINT=$(gcloud ai endpoints list --project=$PROJECT --region=$REGION \
  --filter="displayName:rpc-estimator-endpoint" --format='value(name)')

gcloud ai endpoints describe $ENDPOINT --project=$PROJECT --region=$REGION \
  --format='value(deployedModels[].id,deployedModels[].displayName,deployedModels[].model)'
```

You need at least two `deployedModels` to roll back. If only one is deployed, **stop** — there is no prior to fall back to (skip to §3).

## 2. Shift traffic back

Vertex uses a traffic-split map keyed by deployed-model id. To roll all traffic to the prior `deployedModelId=$PRIOR`:

```bash
gcloud ai endpoints traffic-split set $ENDPOINT \
  --project=$PROJECT --region=$REGION \
  --traffic-split=$PRIOR=100
```

This is reversible; re-running with the new id restores the original split.

## 3. If only one version is deployed (no prior)

Pin scoring-api to the previous Cloud Run revision so the pre-bad-deploy `vertex-endpoint-url` (if it changed) is restored. Cloud Run keeps the previous revision; you don't need to rebuild.

```bash
PREV=$(gcloud run revisions list \
  --project=$PROJECT --region=$REGION \
  --service=scoring-api-$ENV \
  --format='value(metadata.name)' --limit=2 | tail -n1)

gcloud run services update-traffic scoring-api-$ENV \
  --project=$PROJECT --region=$REGION \
  --to-revisions=$PREV=100
```

If the model artifact itself is the issue and there is no prior endpoint deployment, you must re-upload from a known-good `model.bst` in `gs://msm-rpc-rpc-artifacts-$ENV/models/rpc-estimator/<earlier_ts>/` — see `ops/deploy_real_model.py` (run with `--artifact-uri` pointed at the older blob). This is an Owner-ADC operation.

## 4. Verify rollback

- `/v1/score` returns `model_version` matching the rolled-back version.
- `residuals_daily` MAE returns to the prior baseline within one query window.
- No new entries in the breaker log filter (no upstream-induced anomaly).

## 5. After rollback, before the next forward-deploy

- Open an incident note in `docs/incidents/YYYY-MM-DD.md` describing what was different about the rolled-back model (training data window, hyperparameters, or feature changes).
- Don't re-deploy the same artifact without a fix.
