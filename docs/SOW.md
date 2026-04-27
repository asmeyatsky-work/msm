# Statement of Work — Predictive RPC Estimator

**Prepared:** 2026-04-27
**Repo / tag baseline:** `asmeyatsky-work/msm` @ `v0.1.5`
**Target environments:** `staging` (lower), `prod`
**GCP project:** `msm-rpc` (region `europe-west2`)

---

## 1. Background

The Predictive RPC Estimator monorepo (`msm`) implements the architecture in `Predictive RPC Estimator PRD.pdf` under the constraints in `Architectural Rules — 2026.md`. As of `v0.1.5` a complete staging stack is live in `msm-rpc / europe-west2`:

- Cloud Run services: `scoring-api`, `activation`, `reconciliation`, `breaker-automation`
- Vertex AI online endpoint serving a real XGBoost regressor (`rpc-estimator@1`)
- BigQuery dataset `rpc_estimator_staging` (sales ledger, predictions raw + typed view, training-row view)
- Pub/Sub → BigQuery predictions subscription
- GitHub Actions CD on tag push (`v*.*.*`), gated WIF deploy, `staging` and `prod` environments defined
- PRD §5 guardrails: model/BQ timeouts, anomaly threshold, breaker, negative-prediction clamp

Staging answers `/v1/score` end-to-end against a real Vertex model. The model is trained on synthetic data; `/v1/explain` and `prod` are not yet wired. This SOW closes those gaps and delivers a production cutover path.

## 2. Objectives

1. Deliver a fully functional **lower environment** (`staging`) that exercises the production code paths end-to-end against representative data.
2. Deliver a **production environment** (`prod`) provisioned from the same Terraform with parity of services, IAM, alerting, and CD.
3. Deliver the **operational artifacts** (runbooks, SLOs, alerts, rollback) required for on-call ownership.

## 3. Scope

### Phase 1 — Close staging gaps (lower env complete)

| # | Deliverable | Acceptance |
|---|---|---|
| 1.1 | Real `/v1/explain` path: replace `vertex-placeholder.example.com` with a Vertex AI explanation request against the deployed endpoint (or documented SHAP-on-Cloud-Run fallback if explanations aren't enabled on the prebuilt container). | `POST /v1/explain` against staging returns per-feature attributions for a known input within timeout budget; integration test in CI. |
| 1.2 | **Sliding anomaly window**: replace cumulative null-rate counter with a time-bounded sliding window (PRD §5). | Unit + integration test proves the window recovers after the threshold breach clears; staging smoke confirms. |
| 1.3 | **IAM in Terraform**: encode the ad-hoc grants on `scoring-api-staging` SA (`aiplatform.user`, `bigquery.jobUser`, `bigquery.dataViewer`) and the Vertex Service Agent `storage.objectViewer` on the artifacts bucket into `infra/terraform/wif.tf`. | `terraform plan` is empty against the live project; a fresh-project bootstrap from `ops/bootstrap.sh` succeeds without manual grants. |
| 1.4 | **Coverage floor re-enabled**: restore Rust 80% coverage gate in CI. | CI fails a PR that drops coverage below 80%. |
| 1.5 | **Smoke + load profile** for staging: scripted `k6`/`vegeta` profile against `/v1/score` and `/v1/explain` at expected p95 RPS; result captured. | Latency report committed under `ops/perf/`; p95 within PRD §5 budget on staging shape. |

### Phase 2 — Real data path

| # | Deliverable | Acceptance |
|---|---|---|
| 2.1 | **Data contract** for real click + sales-ledger feeds: source system, schema, freshness, PII handling. | Document under `docs/data-contract.md`, signed off by client data owner. |
| 2.2 | **Ingestion** of real (or client-provided sample) data into `rpc_estimator_staging.sales_ledger` and `synthetic_clicks` equivalents — either via Dataform, scheduled query, or Pub/Sub push from the client side. | Daily refresh observed in BQ; row counts match source. |
| 2.3 | **Retrain** `rpc-estimator@2` on real data via the existing `ml-pipeline-train` Job; register a new Vertex model version; deploy behind a canary traffic split. | New model serves ≥10% staging traffic with no breaker trips for 24h; offline metrics tracked in BQ. |
| 2.4 | **Drift / quality monitoring** on the predictions stream (PSI on inputs, residuals on outputs vs. ledger). | BigQuery scheduled job + dashboard tile. |

### Phase 3 — Production cutover

| # | Deliverable | Acceptance |
|---|---|---|
| 3.1 | **Prod Terraform workspace** in a separate state bucket; provisioning of: project (or shared), WIF pool/provider `github-prod`, prod SAs, Artifact Registry, BQ dataset `rpc_estimator_prod`, Vertex endpoint, Pub/Sub, Cloud Run services. | `terraform apply` green; resources visible in console. |
| 3.2 | **Prod CD enablement**: set `vars.DEPLOY_PROD=true`, configure GH `prod` environment with required reviewers, prod-tier secrets (`GCP_WIF_PROVIDER_PROD`, `GCP_CI_SA_PROD`, `TF_STATE_BUCKET_PROD`). | Tag push deploys staging then prompts for prod approval; approval deploys prod. |
| 3.3 | **Prod-tier configuration**: `ANOMALY_THRESHOLD=0.03`, prod `MODEL_TIMEOUT_MS`/`BQ_TIMEOUT_MS`, Cloud Run min-instances and concurrency tuned from Phase 1.5 load profile. | Values applied via Terraform, not console. |
| 3.4 | **Observability**: SLOs (availability, p95 latency, breaker trip rate), Cloud Monitoring alert policies, log-based metrics, on-call routing. | Alerts fire in a synthetic incident drill. |
| 3.5 | **Runbooks** under `docs/runbooks/`: breaker reset, model rollback (Vertex traffic split), endpoint scale-down for cost, secret rotation, BQ schema migration. | Reviewed with client on-call. |
| 3.6 | **Rollback plan**: documented Vertex traffic-split rollback to prior model version; Cloud Run revision pin; BQ snapshot restore steps. | Dry-run executed in staging. |
| 3.7 | **Cutover**: shadow prod traffic for 7 days, then primary; sign-off. | Client sign-off email. |

## 4. Out of scope

- Net-new ML models beyond the existing XGBoost regressor.
- Multi-region active-active (single region `europe-west2` only).
- Customer-managed encryption keys (CMEK) — Google-managed only unless client requires.
- UI / dashboard work beyond what already exists in `dashboard/`.
- Migration of historical data older than the agreed contract window.

## 5. Assumptions

- Client provides access to the real click and sales-ledger source within Phase 2 kickoff +5 business days.
- Client provides a prod GCP project (or authorises use of `msm-rpc` with prod-isolated resources).
- One named client data owner and one named on-call engineer for sign-off.
- GitHub branch protection on `main` (8 required CI contexts) is retained.
- Vertex AI online endpoint at min=1 remains the cost baseline (~£0.08/hr/replica); prod will be sized from Phase 1.5.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Real data shape diverges from synthetic schema, breaking the trained model. | Phase 2.1 data contract precedes 2.3 retrain; schema diff gate in Dataform. |
| Vertex prebuilt XGBoost container doesn't expose explanations. | Phase 1.1 has a SHAP-on-Cloud-Run fallback; decision recorded in ADR. |
| Prod IAM bootstrap requires Owner once. | Documented in `ops/bootstrap.sh`; one-time client-side action. |
| Cost of a second always-on Vertex endpoint in prod. | Phase 3.3 right-sizes from load profile; min-instances tunable per env. |

## 7. Milestones (indicative)

| Milestone | Calendar weeks |
|---|---|
| Phase 1 complete (staging gaps closed) | 2 weeks |
| Phase 2 complete (real data, retrained model in staging) | +3 weeks (gated on client data access) |
| Phase 3 complete (prod live, signed off) | +3 weeks |
| **Total** | **~8 weeks** from kickoff, gated on client dependencies |

## 8. Acceptance

The SOW is complete when:
1. `staging` serves `/v1/score` and `/v1/explain` against real-data-trained `rpc-estimator@2` with all PRD §5 guardrails active.
2. `prod` is provisioned from Terraform, deployed via approved CD, and serving traffic within SLO for 7 consecutive days.
3. Runbooks, alerts, and rollback procedure have passed a drill.
4. Client on-call has accepted handover.
