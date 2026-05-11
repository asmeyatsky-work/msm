# Predictive RPC Estimator

End-to-end revenue-per-click (RPC) forecasting service. Predicts realized revenue for
each click in near real-time so bidding and budget decisions can use a forward signal
instead of the lagging sales-ledger reconciliation.

Authoritative documents:

- `Predictive RPC Estimator PRD.pdf` — product requirements.
- `Architectural Rules — 2026.md` — hard architectural rules. Deviations live as ADRs in `docs/adr/`.
- `docs/SOW.md` — Statement of Work and phase plan.
- `docs/data-contract.md` — schema, freshness and PII handling for client data feeds.
- `docs/runbooks/` — operational runbooks (breaker, rollback, scale-down, secret rotation).

## Bounded contexts and services

| Context           | Component                      | Stack          | Runtime                | Role |
|-------------------|--------------------------------|----------------|------------------------|------|
| Scoring           | `services/scoring-api`         | Rust 1.89      | Cloud Run              | Hot-path click → bounded RPC prediction; PRD §5 guardrails. |
| Scoring           | `services/bounds-calibration`  | Rust           | Cloud Run job          | Computes per-segment RPC bounds used by the scoring service. |
| ML Ops            | `services/ml-pipeline`         | Python 3.12    | Vertex AI Pipelines    | Training, feature engineering, model registry, retrain. |
| Activation        | `services/activation`          | Python 3.12    | Cloud Run              | Bridge to SA360 / SSGTM / OCI. |
| Reconciliation    | `services/reconciliation`      | Python 3.12 (FastAPI) | Cloud Run       | Reads `predictions_vs_revenue`; serves the dashboard API. |
| Reconciliation    | `dashboard/`                   | TypeScript + React (Vite) + nginx | Cloud Run | Executive dashboard; reverse-proxies `/api` to reconciliation. |
| Resilience        | `services/breaker-automation`  | Python 3.12    | Cloud Run / functions  | Consumes anomaly events, flips the circuit-breaker config. |
| Testing fixtures  | `services/mock-vertex`         | Python         | retired (replaced by real Vertex endpoint) | Historical mock; kept for local contract tests. |

Each in-scope bounded context has one MCP server (`mcp-servers/scoring-mcp`, `mcp-servers/mlops-mcp`).

## Hot path

```
Client → scoring-api (Cloud Run)
         ├── Vertex AI endpoint (XGBoost regressor)         — predicted_rpc
         ├── BigQuery (feature lookups, timeouts §3.2)
         └── Pub/Sub topic rpc-predictions-staging          — every prediction
                ↓
        BigQuery subscription rpc-predictions-bq-staging
                ↓
        rpc_predictions_raw (table) → rpc_predictions (view, JSON-unpacked)
                ↘ joined with sales_ledger → predictions_vs_revenue (view)
                                                  ↓
                            reconciliation API → dashboard (UI)
```

## Layer direction (Architectural Rule §2)

```
domain ← application ← infrastructure
                    ← presentation
```

Enforced in CI: `import-linter` (Python), Cargo workspace boundaries + `cargo-deny` (Rust),
`eslint-plugin-boundaries` (TypeScript). Rule not in CI = rule not real (§2).

## Safety guardrails (PRD §5)

Implemented in `services/scoring-api/crates/domain` and configured via Cloud Run env:

- **Prediction bounds** — hard min/max RPC per segment; out-of-range outputs are clamped or rejected.
- **Negative-prediction clamp** — XGBoost can produce small negatives on OOD inputs; clamped at 0 before domain construction.
- **Model and BigQuery timeouts** — `MODEL_TIMEOUT_MS`, `BQ_TIMEOUT_MS` (per-env).
- **Anomaly detection** — null/zero-rate threshold (`ANOMALY_THRESHOLD`, staging 0.50, prod default 0.03). Cumulative window today; sliding window is a known follow-up.
- **Circuit breaker** — on threshold breach, falls back to data-layer revenue and emits a `rpc-anomaly-staging` event; `breaker-automation` consumes it and updates the kill-switch flag without a deploy.
- **Kill switch** — single config flag, no redeploy required.

## Deployment topology — staging (`msm-rpc`, region `europe-west2`)

| Layer | Resource | Identifier |
|-------|----------|------------|
| Cloud Run | `scoring-api-staging` | `scoring-api-staging-794974391956.europe-west2.run.app` |
| Cloud Run | `reconciliation-staging` | `reconciliation-staging-794974391956.europe-west2.run.app` |
| Cloud Run | `dashboard-staging` | `dashboard-staging-794974391956.europe-west2.run.app` |
| Cloud Run | `activation-staging` | `activation-staging-794974391956.europe-west2.run.app` |
| Cloud Run | `breaker-automation-staging` | `breaker-automation-staging-794974391956.europe-west2.run.app` |
| Vertex AI | Model `rpc-estimator@1` | `projects/794974391956/locations/europe-west2/models/7377296411865382912` |
| Vertex AI | Endpoint `rpc-estimator-endpoint` | `projects/794974391956/locations/europe-west2/endpoints/4471390533746425856`, `e2-standard-2`, min=1 |
| Pub/Sub | Topics | `rpc-clicks-staging`, `rpc-predictions-staging`, `rpc-anomaly-staging`, `rpc-audit-staging` |
| Pub/Sub | Subscriptions | `rpc-clicks-bq-staging`, `rpc-predictions-bq-staging`, `rpc-anomaly-to-breaker-staging` |
| BigQuery | Dataset | `msm-rpc:rpc_estimator_staging` |
| BigQuery | Tables | `cm360_clicks_raw`, `rpc_predictions_raw`, `sales_ledger`, `sales_ledger_synthetic`, `synthetic_clicks` |
| BigQuery | Views | `cm360_clicks`, `rpc_predictions`, `rpc_training_rows`, `predictions_vs_revenue` |
| Storage | TF state | `gs://msm-rpc-rpc-tf-state-staging` |
| Storage | Model artifacts | `gs://msm-rpc-rpc-artifacts-staging` (Vertex SA has `roles/storage.objectViewer`) |
| Artifact Registry | Images | `europe-west2-docker.pkg.dev/msm-rpc/rpc-estimator/{scoring-api,reconciliation,activation,breaker-automation,ml-pipeline,dashboard}` |
| Drift / quality | Dataform | `dataform/definitions/` — scheduled PSI on inputs and residuals on outputs |

### Service accounts

- `scoring-api-staging@msm-rpc.iam.gserviceaccount.com` — scoring-api, reconciliation, dashboard, ml-pipeline-train.
- `activation-staging@msm-rpc.iam.gserviceaccount.com` — activation.
- `breaker-automation-staging@msm-rpc.iam.gserviceaccount.com` — breaker, plus `secretmanager.secretVersionAdder`.
- `ci-deployer-staging@msm-rpc.iam.gserviceaccount.com` — assumed by GitHub Actions via WIF.

### Production

Prod Terraform workspace exists (`infra/terraform/envs/prod.tfvars`), images and roles parameterised.
Deploys are gated on the GitHub Actions repository variable `vars.DEPLOY_PROD`, currently unset by intent.
Bootstrap, model deployment, load profile capture, and notification wiring are scripted via
`ops/owner-actions.sh`.

## Observed performance — staging

Measured 2026-04-28 against the live endpoint (`oha`, 30 s @ c=10):

| Endpoint | p50 | p95 | p99 | Errors |
|---|---|---|---|---|
| `POST /v1/score`   | 561 ms | 762 ms | 993 ms | 0% (latest run; earlier 7.4% during autoscale) |
| `POST /v1/explain` | 1.34 s | 1.82 s | 2.11 s | 21.1% (mostly client-side timeouts; raised to 3 s post-run) |

Vertex round-trip is the dominant cost; Cloud Run overhead is negligible. Prod must use a
larger Vertex machine and min replicas ≥ 2 — see `infra/terraform/envs/prod.tfvars`.

Raw results in `ops/perf/`.

## Repo layout

```
.
├── Architectural Rules — 2026.md     # Hard rules
├── Predictive RPC Estimator PRD.pdf  # Product spec
├── README.md
├── contract-tests/                   # Cross-service Pact tests
├── dashboard/                        # React + nginx; deployed as dashboard-staging
├── dataform/                         # SQLX models, drift monitors, scheduled queries
├── docs/
│   ├── SOW.md
│   ├── adr/                          # Architecture Decision Records
│   ├── data-contract.md
│   ├── runbooks/
│   ├── client-demo-deck.pptx         # Client-facing demo deck
│   └── searce-build-overview.pptx    # Searce-internal build deck
├── infra/terraform/                  # GCP IaC (cloud_run.tf, monitoring.tf, wif.tf, envs/)
├── mcp-servers/                      # One per bounded context (§3.5)
│   ├── mlops-mcp/
│   └── scoring-mcp/
├── ops/
│   ├── bootstrap.sh                  # First-time IAM/state bucket bootstrap
│   ├── deploy_real_model.py          # Trains + registers Vertex model
│   ├── owner-actions.sh              # Owner-ADC entry point (deploy-model, load-test, …)
│   ├── ingestion/                    # Real-data ingestion templates
│   ├── e2e/                          # End-to-end smoke
│   ├── load/                         # Load profiles
│   ├── perf/                         # Captured perf results
│   └── rollback/                     # Vertex traffic-split rollback helpers
├── proto/                            # Cross-service contracts (§1)
└── services/
    ├── activation/                   # Python — SA360/SSGTM bridge
    ├── bounds-calibration/           # Rust — per-segment RPC bounds job
    ├── breaker-automation/           # Python — anomaly → breaker
    ├── ml-pipeline/                  # Python — training, drift, retrain
    ├── mock-vertex/                  # Retired test fixture
    ├── reconciliation/               # Python (FastAPI) — predictions_vs_revenue API
    └── scoring-api/                  # Rust — hot path, p95 ~760 ms
```

## CI / CD

- GitHub Actions; tag push `v*.*.*` triggers `.github/workflows/cd.yml` which deploys staging.
- Production deploy is the same workflow, gated on `vars.DEPLOY_PROD == 'true'` and the `prod` environment's required-reviewers (unset by intent).
- Authentication via Workload Identity Federation — no long-lived service-account keys in CI.
- Coverage and architectural-boundary gates run on every PR; supply-chain scans (`cargo-deny`, `pip-audit`, `npm audit`) run in CI.

## Local development

```
# Dashboard
cd dashboard && npm ci && npm run dev    # localhost:5173, proxies /api → reconciliation-staging

# Scoring API
cd services/scoring-api && cargo run -p presentation

# Reconciliation
cd services/reconciliation && pip install -e . && uvicorn msm_reconciliation.presentation.main:app
```

macOS hot-path tools: `brew install libomp` (XGBoost native deps for `ops/deploy_real_model.py`).
