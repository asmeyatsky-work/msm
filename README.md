# Predictive RPC Estimator

Production build of the Predictive Revenue-Per-Click (RPC) Estimator. Scores SA360 clicks
in near real-time with predicted revenue, enabling value-based bidding (tROAS).

See [`docs/prd.pdf`](../Predictive%20RPC%20Estimator%20PRD.pdf) for the full PRD and
[`../Architectural Rules — 2026.md`](../Architectural%20Rules%20%E2%80%94%202026.md)
for hard rules. All deviations captured as ADRs in `docs/adr/`.

## Bounded contexts

| Context         | Service                | Stack      | Purpose                                                    |
|-----------------|------------------------|------------|------------------------------------------------------------|
| Scoring         | `services/scoring-api` | Rust       | Hot-path click → bounded RPC prediction (p99 < 50ms)       |
| ML Ops          | `services/ml-pipeline` | Python 3.12| Training, feature eng, Vertex AI registry, drift detection |
| Activation      | `services/activation`  | Python 3.12| SSGTM/OCI bridge — writes predictions to SA360             |
| Reconciliation  | `dashboard/`           | TS + React | Looker-adjacent UI for prediction vs. realized revenue     |

Each bounded context has exactly one MCP server (§3.5).

## Layer direction (§2)

```
domain ← application ← infrastructure
                    ← presentation
```

Enforced in CI: `import-linter` (Py), Cargo workspace boundaries + `cargo-deny` (Rust),
`eslint-plugin-boundaries` (TS). Rule not in CI = rule not real (§2).

## Safety guardrails (PRD §5 — first-class)

Implemented in `services/scoring-api/crates/domain`:
- Prediction bounds (hard min/max RPC)
- Kill switch (single config flag, no deploy)
- Circuit breaker (automated fallback to data-layer revenue)
- Anomaly detection hook (null/zero rate > 3% → breaker)

## Repo layout

```
.
├── docs/adr/                       # Architecture Decision Records
├── proto/                          # Cross-service contracts (§1)
├── services/
│   ├── scoring-api/                # Rust workspace, hot path
│   ├── ml-pipeline/                # Python, training + feature store
│   └── activation/                 # Python, SSGTM bridge
├── mcp-servers/                    # One per bounded context (§3.5)
├── dashboard/                      # Reconciliation UI
├── infra/terraform/                # GCP IaC
└── .github/workflows/              # CI (coverage, boundaries, supply-chain)
```
