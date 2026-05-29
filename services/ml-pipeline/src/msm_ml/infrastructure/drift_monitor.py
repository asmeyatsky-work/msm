"""DriftMonitor adapters. Layer: infrastructure. Implements application.DriftMonitor.
§4: Workload Identity, query timeout, no PII.

`InMemoryDriftMonitor` is the in-memory/test adapter (§3.2). `BigQueryDriftMonitor`
reads PSI from the monitoring layer (dataform `psi_daily`) — scaffolded; the
query is a TODO. No concrete DriftMonitor existed before this agent work.
"""
from __future__ import annotations
from typing import Sequence

import structlog

from msm_ml.application.ports import DriftMonitor
from msm_ml.domain import DriftScore

_log = structlog.get_logger()


class InMemoryDriftMonitor(DriftMonitor):
    def __init__(self, scores: Sequence[DriftScore]) -> None:
        self._scores = tuple(scores)

    def score(self, baseline_window_ms: int, current_window_ms: int) -> Sequence[DriftScore]:
        return self._scores


class BigQueryDriftMonitor(DriftMonitor):
    def __init__(self, project: str, dataset: str, *, query_timeout_s: float = 30.0) -> None:
        self._project = project
        self._dataset = dataset
        self._query_timeout_s = query_timeout_s

    def score(self, baseline_window_ms: int, current_window_ms: int) -> Sequence[DriftScore]:
        # TODO(agentic-ops): SELECT feature_name, psi FROM `{project}.{dataset}.psi_daily`
        # for the current window vs baseline, bounded by query_timeout_s. Returns []
        # on failure so triage degrades to "no drift observed" rather than blocking.
        _log.warning("drift_monitor_stub", baseline_window_ms=baseline_window_ms,
                     current_window_ms=current_window_ms, note="returning no scores — not yet wired")
        return ()
