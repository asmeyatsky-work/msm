"""SignalSource adapters. Layer: infrastructure. Implements application.SignalSource.
§4: Workload Identity only; explicit query timeout; no PII.

`MonitoringSignalSource` reads the most recent per-feature PSI from the dataform
`psi_daily` table and surfaces features at/above the moderate-shift threshold
(0.1) as correlated signals — so breaker triage can answer "what else was
drifting when this tripped?". `InMemorySignalSource` is the test adapter (§3.2).
"""
from __future__ import annotations
from typing import Sequence

import structlog
from google.cloud import bigquery

from msm_breaker.application.ports import SignalSource
from msm_breaker.domain import Signal

_log = structlog.get_logger()

_MODERATE_PSI = 0.1


class InMemorySignalSource(SignalSource):
    def __init__(self, signals: Sequence[Signal]) -> None:
        self._signals = tuple(signals)

    def recent(self, window_ms: int) -> Sequence[Signal]:
        return self._signals


class MonitoringSignalSource(SignalSource):
    def __init__(self, project: str, dataset: str, *, query_timeout_s: float = 10.0) -> None:
        self._client = bigquery.Client(project=project)
        self._project = project
        self._dataset = dataset
        self._query_timeout_s = query_timeout_s

    def recent(self, window_ms: int) -> Sequence[Signal]:
        sql = f"""
        WITH latest AS (
          SELECT MAX(as_of_date) AS d FROM `{self._project}.{self._dataset}.psi_daily`
        )
        SELECT feature, psi,
               UNIX_MILLIS(TIMESTAMP(latest.d)) AS observed_at_ms
        FROM `{self._project}.{self._dataset}.psi_daily`, latest
        WHERE as_of_date = latest.d AND psi >= @thr
        QUALIFY model_version = MAX(model_version) OVER ()
        """
        try:
            job = self._client.query(
                sql,
                job_config=bigquery.QueryJobConfig(query_parameters=[
                    bigquery.ScalarQueryParameter("thr", "FLOAT64", _MODERATE_PSI),
                ]),
                timeout=self._query_timeout_s,  # §3.2
            )
            return [
                Signal(name=f"psi:{row['feature']}", value=float(row["psi"] or 0.0),
                       threshold=_MODERATE_PSI, observed_at_ms=int(row["observed_at_ms"] or 0))
                for row in job.result(timeout=self._query_timeout_s)
            ]
        except Exception as e:  # noqa: BLE001 — degrade to verdict-only triage
            _log.warning("signal_source_query_failed", error=str(e))
            return ()
