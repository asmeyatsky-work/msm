# Runbook — Scale down the Vertex endpoint to save cost

**When to use**
- "Save staging costs over the weekend / holiday."
- Suspending an env that is not actively being demo'd.

The Vertex AI online endpoint is the dominant cost line: e2-standard-2, min=1 ⇒ ~£0.08/hr/replica continuously. Scaling min replicas to 0 takes the bill near zero; the trade is a 2-3 minute cold start when the endpoint is next called.

## 1. Identify the deployed model

```bash
PROJECT=msm-rpc
REGION=europe-west2
ENV=staging
ENDPOINT=$(gcloud ai endpoints list --project=$PROJECT --region=$REGION \
  --filter="displayName:rpc-estimator-endpoint" --format='value(name)')
DEPLOYED_ID=$(gcloud ai endpoints describe $ENDPOINT \
  --project=$PROJECT --region=$REGION \
  --format='value(deployedModels[0].id)')
```

## 2. Scale to 0 (or back up)

There is no public `gcloud` for `mutateDeployedModel`; use the REST endpoint. To go to **0 min replicas**:

```bash
gcloud ai endpoints raw-predict --help >/dev/null 2>&1 # ensures auth
TOKEN=$(gcloud auth print-access-token)

curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "deployedModel": {"id":"'$DEPLOYED_ID'", "dedicatedResources":{"minReplicaCount":0,"maxReplicaCount":1,"machineSpec":{"machineType":"e2-standard-2"}}},
        "updateMask":"dedicatedResources.minReplicaCount"
      }' \
  "https://$REGION-aiplatform.googleapis.com/v1/$ENDPOINT:mutateDeployedModel"
```

Restore (back to `min=1`) by repeating with `"minReplicaCount":1`.

## 3. Side-effects to expect

- First `/v1/score` after scale-up takes 2-3 min and may hit `MODEL_TIMEOUT_MS` (500 ms). The breaker will trip. Manually warm the endpoint before sending real traffic:
  ```bash
  gcloud ai endpoints predict $ENDPOINT --project=$PROJECT --region=$REGION \
    --json-request=ops/perf/sample-instance.json
  ```
- Any monitoring alert that fires during the down-window will be noise; silence them in Cloud Monitoring before scaling down.

## 4. Verify

- `gcloud ai endpoints describe …` shows `minReplicaCount: 0` (or `1` when restored).
- After scale-up + warm, `/v1/score` returns `source: MODEL` end-to-end.
