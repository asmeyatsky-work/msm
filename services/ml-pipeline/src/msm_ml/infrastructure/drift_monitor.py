"""DriftMonitor adapters. Layer: infrastructure. Implements application.DriftMonitor.
§4: Workload Identity, query timeout, no PII.

`BigQueryDriftMonitor` reads the dataform `psi_daily` monitoring table (PSI per
numeric feature, live clicks vs training baseline). `InMemoryDriftMonitor` is the
in-memory/test adapter (§3.2). No concrete DriftMonitor existed before the agent
work — DetectDrift had only the port.
"""
from __future__ import annotations
from typing import Sequence

import structlog
from google.cloud import bigquery

from msm_ml.application.ports import DriftMonitor
from msm_ml.domain import DriftScore

_log = structlog.get_logger()


class InMemoryDriftMonitor(DriftMonitor):
    def __init__(self, scores: Sequence[DriftScore]) -> None:
        self._scores = tuple(scores)

    def score(self, baseline_window_ms: int, current_window_ms: int) -> Sequence[DriftScore]:
        return self._scores


class BigQueryDriftMonitor(DriftMonitor):
    """Reads PSI for the most recent `as_of_date` on or before `current_window_ms`.

    `psi_daily` already compares live clicks against the per-model training
    baseline, so `baseline_window_ms` is informational only — the baseline is the
    `feature_baseline` snapshot, not a click window. Picks the latest model
    version present on that date (QUALIFY). Returns () on any failure so triage
    degrades to "no drift observed" rather than blocking.
    """

    def __init__(self, project: str, dataset: str, *, query_timeout_s: float = 30.0) -> None:
        self._client = bigquery.Client(project=project)
        self._project = project
        self._dataset = dataset
        self._query_timeout_s = query_timeout_s

    def score(self, baseline_window_ms: int, current_window_ms: int) -> Sequence[DriftScore]:
        sql = f"""
        WITH latest AS (
          SELECT MAX(as_of_date) AS d
          FROM `{self._project}.{self._dataset}.psi_daily`
          WHERE as_of_date <= DATE(TIMESTAMP_MILLIS(@cur))
        )
        SELECT feature, psi
        FROM `{self._project}.{self._dataset}.psi_daily`, latest
        WHERE as_of_date = latest.d
        QUALIFY model_version = MAX(model_version) OVER ()
        """
        try:
            job = self._client.query(
                sql,
                job_config=bigquery.QueryJobConfig(query_parameters=[
                    bigquery.ScalarQueryParameter("cur", "INT64", current_window_ms),
                ]),
                timeout=self._query_timeout_s,  # §3.2
            )
            return [
                DriftScore(feature_name=str(row["feature"]), psi=float(row["psi"] or 0.0))
                for row in job.result(timeout=self._query_timeout_s)
            ]
        except Exception as e:  # noqa: BLE001 — degrade, don't block the pipeline
            _log.warning("drift_monitor_query_failed", error=str(e))
            return ()
