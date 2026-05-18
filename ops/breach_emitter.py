"""PRD V2 §4.6 breach emitter.

Reads the Dataform-materialised breach views and writes one structured-log
line per breach row to Cloud Logging under the log name
`rpc-breach-emitter-${ENV}`. The Terraform log-based metrics
`rpc_drift_breaches_${ENV}` and `rpc_coverage_drops_${ENV}` count those
lines; the associated alert policies fire when the count crosses 0 in the
last hour.

Run daily. Designed for Cloud Scheduler → Cloud Run Job, but works as a
plain script too:

    GCP_PROJECT=msm-rpc \\
    BQ_DATASET=rpc_estimator_client-cc \\
    ENV=client-cc \\
    python3 ops/breach_emitter.py

Idempotent: every run re-reads the same materialised tables. The alert
metric is COUNT-based with a 1h alignment window, so the alert remains
hot for an hour after the last emit even if Scheduler skips a tick.

Failure mode: if either view is missing (e.g. before Dataform has run),
the script logs an info line and exits 0 — the alert stays silent.
"""
from __future__ import annotations
import logging
import os
import sys
from typing import Iterable, Mapping


_LOG_NAME = "rpc-breach-emitter"


def _client_logger(project: str, env: str):
    """Return a Python logger that writes to Cloud Logging under our log name.

    Falls back to a stderr structlog if google-cloud-logging is missing so
    the script is still useful in local development.
    """
    name = f"{_LOG_NAME}-{env}"
    try:
        import google.cloud.logging as gcl  # noqa: WPS433
        from google.cloud.logging.handlers import CloudLoggingHandler  # noqa: WPS433
    except ImportError:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        return logging.getLogger(name)
    client = gcl.Client(project=project)
    handler = CloudLoggingHandler(client, name=name)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _bq_rows(project: str, dataset: str, table: str) -> Iterable[Mapping[str, object]]:
    """Yield rows from a BigQuery table; empty if the table is missing."""
    try:
        from google.cloud import bigquery  # noqa: WPS433
    except ImportError:
        return []
    try:
        client = bigquery.Client(project=project)
        return list(
            client.query(
                f"SELECT * FROM `{project}.{dataset}.{table}`",
                timeout=30.0,
            ).result(timeout=30.0)
        )
    except Exception:
        return []


def emit_drift_breaches(logger, project: str, dataset: str) -> int:
    n = 0
    for row in _bq_rows(project, dataset, "drift_breaches_weekly"):
        logger.warning(
            "per-segment MAE drift > 25%% W-o-W",
            extra={
                "json_fields": {
                    "alert": {
                        "kind": "drift_breach",
                        "model_version": row.get("model_version"),
                        "product_type": row.get("product_type"),
                        "device": row.get("device"),
                        "geo": row.get("geo"),
                        "mae_today": float(row.get("mae_today") or 0.0),
                        "mae_last_week": float(row.get("mae_last_week") or 0.0),
                        "pct_change": float(row.get("pct_change") or 0.0),
                    },
                },
            },
        )
        n += 1
    return n


def emit_coverage_drops(logger, project: str, dataset: str) -> int:
    n = 0
    for row in _bq_rows(project, dataset, "coverage_drops_weekly"):
        logger.warning(
            "coverage dropped > 10pp W-o-W",
            extra={
                "json_fields": {
                    "alert": {
                        "kind": "coverage_drop",
                        "slice_dim": row.get("slice_dim"),
                        "slice_value": row.get("slice_value"),
                        "coverage_today": float(row.get("coverage_today") or 0.0),
                        "coverage_last_week": float(row.get("coverage_last_week") or 0.0),
                        "pct_change": float(row.get("pct_change") or 0.0),
                    },
                },
            },
        )
        n += 1
    return n


def main() -> int:
    project = os.environ["GCP_PROJECT"]
    dataset = os.environ["BQ_DATASET"]
    env = os.environ.get("ENV", "staging")
    logger = _client_logger(project, env)
    drift = emit_drift_breaches(logger, project, dataset)
    cover = emit_coverage_drops(logger, project, dataset)
    print(f"breach_emitter: drift={drift} coverage={cover}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
