# Runbook — Reset the anomaly breaker

**Symptom**
- Alert: *scoring-api {env} — anomaly breaker tripped*, OR
- `/v1/score` is returning fallback predictions (`source: FALLBACK_DATA_LAYER`) for every request.

## 1. Confirm

```bash
ENV=staging  # or prod
PROJECT=msm-rpc

# Look for the structured warning that fires the log-based metric.
gcloud logging read --project=$PROJECT --limit=20 \
  'resource.type="cloud_run_revision"
   resource.labels.service_name="scoring-api-'$ENV'"
   jsonPayload.message=~"anomaly window breached"' \
  --format='value(timestamp,jsonPayload.message)'
```

If you see no recent entries, the alert is stale — clear it and stop. If you do, continue.

## 2. Diagnose

Three causes, in order of likelihood:

1. **Real upstream issue**: Vertex endpoint is returning many `0.0` predictions.
   - Check Vertex endpoint health and recent deployments.
   - Read recent prediction logs (`source: MODEL`) and look at `predicted_rpc` distribution in `rpc_predictions`.
2. **Data-quality issue**: incoming clicks have many out-of-spec features (cerberus_score outside [0,1], etc.).
   - Look at `dataform/definitions/monitoring/psi_daily.sqlx` output — a `major_shift` row is a strong tell.
3. **Threshold mis-set**: prod sometimes ships a model whose null-rate sits naturally above the 0.03 floor for a brief window.
   - Check the `ANOMALY_THRESHOLD` env on the latest revision: `gcloud run services describe scoring-api-$ENV --region=europe-west2 --format='value(spec.template.spec.containers[0].env)'`.

## 3. Fix

The breaker is sticky-by-design. Cool-off auto-recovers after 30 s once the underlying signal clears, but a wedge-open state needs a deliberate reset.

- **Auto-reset (preferred)** — once the upstream is fixed, the sliding window ages out the bad samples (ANOMALY_WINDOW_SECS=300 by default). Verify by hitting `/v1/score` and checking the response `source` flips back to `MODEL`.
- **Force reset** — restart the Cloud Run revision; the in-memory breaker state resets to `Closed`:
  ```bash
  gcloud run services update scoring-api-$ENV \
    --project=$PROJECT --region=europe-west2 \
    --update-labels=breaker-reset=$(date +%s)
  ```

## 4. Verification

- `/v1/score` returns `source: MODEL` for two consecutive requests.
- Cloud Monitoring `scoring-api {env} — anomaly breaker tripped` returns to OK within 5 min.
- New row in `rpc_predictions` view with `source = "MODEL"` and a non-zero `predicted_rpc`.
