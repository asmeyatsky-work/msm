# ADR 0002 — `/v1/explain` path

**Status:** Accepted — 2026-04-27
**Context tag:** `v0.1.6` (in flight, post-`v0.1.5`)

## Context

`scoring-api` exposes `/v1/explain` for per-feature SHAP attributions on a scored click. Through `v0.1.5` the route was wired (`ExplainEndpoint` port + `VertexExplain` adapter + `ExplainClick` use case), but `VERTEX_EXPLAIN_URL` was a Terraform-managed placeholder pointing at `vertex-placeholder.example.com`. The score path was real; the explain path was not.

Two questions to answer:

1. **How should the explain URL be configured?** A second secret duplicates `vertex-endpoint-url-${env}`; a placeholder env var is a known foot-gun (we hit it on first deploy).
2. **Does the deployed model actually support `:explain`?** Vertex AI's prebuilt XGBoost prediction container (`europe-docker.pkg.dev/vertex-ai/prediction/xgboost-cpu.1-7`) only serves `:explain` if the model was uploaded with an `explanationSpec`. `rpc-estimator@1` was uploaded without one.

## Decision

### Configuration

`scoring-api` derives `VERTEX_EXPLAIN_URL` at startup from `VERTEX_ENDPOINT_URL` by replacing the trailing `:predict` with `:explain` (or `/predict` → `/explain` for non-Vertex backends used in tests). The `VERTEX_EXPLAIN_URL` env var still wins if explicitly set — keeps the door open for separately-hosted explanation services without churning the deploy.

The placeholder env in `infra/terraform/cloud_run.tf` is removed.

### Backend: enable Vertex explanations on `rpc-estimator`

Re-upload the existing model with a sampled-Shapley `explanationSpec` and redeploy in place of `rpc-estimator@1`. No code change in `services/scoring-api`; the wire format that `VertexExplain` already parses (`explanations[0].attributions[0].featureAttributions`) matches Vertex's response.

Concrete ops step (one-shot, run from a session with project-Owner ADC):

```bash
gcloud ai models upload \
  --region=europe-west2 \
  --display-name=rpc-estimator \
  --container-image-uri=europe-docker.pkg.dev/vertex-ai/prediction/xgboost-cpu.1-7:latest \
  --artifact-uri=gs://msm-rpc-rpc-artifacts-staging/models/rpc-estimator/<latest>/ \
  --explanation-method=sampled-shapley \
  --explanation-path-count=10 \
  --explanation-metadata-file=ops/explanation_metadata.json
```

`ops/explanation_metadata.json` lists the 14 input features that `VertexEndpoint` already serializes. The new model version is then deployed to the existing endpoint resource (`projects/794974391956/locations/europe-west2/endpoints/4471390533746425856`) with a 10% traffic split for soak, then 100%.

### Fallback: SHAP on Cloud Run (rejected, recorded for completeness)

Loading the `model.bst` artifact into a SHAP-enabled Python sidecar on Cloud Run was considered. Rejected because:

- It duplicates the model artifact in two services (drift risk).
- Vertex's sampled-Shapley already gives the same answer Vertex serves to its own dashboard — better operational consistency.
- The cost of a sidecar at min=1 (~£0.02/hr) is comparable to the Vertex explanation surcharge.

Revisit only if Vertex explanations turn out to exceed PRD §5's latency budget under load (Phase 1.5 will measure).

## Consequences

- One source of truth for the endpoint URL (`vertex-endpoint-url-${env}` secret).
- `/v1/explain` becomes a real call once the re-uploaded model is deployed; integration test in `tests/adapters_integration.rs` already covers the wire format.
- The model re-upload is a one-time ops step tracked under Phase 1.1 acceptance — without it, `:explain` will return a Vertex-side 4xx and the existing `VertexExplain` error path returns a clean 5xx to clients.
- Sampled-shapley with `paths=10` adds ~50–150 ms per `:explain` call. Acceptable: explain is not on the hot scoring path.
