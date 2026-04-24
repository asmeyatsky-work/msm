"""msm-ml — ML Ops bounded context for the Predictive RPC Estimator.

Layer layout (§2):
    domain          — pure feature/target types, no SDKs
    application     — training/inference use cases, port interfaces
    infrastructure  — Vertex AI, BigQuery, GCS adapters
    presentation    — CLI entry points, MCP server wiring
"""
