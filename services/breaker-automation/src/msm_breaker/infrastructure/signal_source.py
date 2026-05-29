"""SignalSource adapters. Layer: infrastructure. Implements application.SignalSource.
§4: Workload Identity only; every external call timeout-bounded.

`MonitoringSignalSource` is the production adapter (Cloud Monitoring / BigQuery
monitoring tables — see dataform/definitions/monitoring/*). It is scaffolded:
the query wiring is a TODO to be filled against the real metric descriptors.
`InMemorySignalSource` is the test/in-memory adapter (§3.2 — tests use in-memory
adapters).
"""
from __future__ import annotations
from typing import Sequence

import structlog

from msm_breaker.application.ports import SignalSource
from msm_breaker.domain import Signal

_log = structlog.get_logger()


class InMemorySignalSource(SignalSource):
    def __init__(self, signals: Sequence[Signal]) -> None:
        self._signals = tuple(signals)

    def recent(self, window_ms: int) -> Sequence[Signal]:
        return self._signals


class MonitoringSignalSource(SignalSource):
    """Reads correlated signals from the monitoring layer.

    TODO(agentic-ops): wire to the Cloud Monitoring API / the
    `psi_daily` + `residuals_daily` monitoring tables. Must apply an explicit
    request timeout (§4) and emit zero PII (§6). Returns [] on any upstream
    failure so triage degrades to "verdict-only" rather than blocking.
    """

    def __init__(self, project: str, *, timeout_s: float = 5.0) -> None:
        self._project = project
        self._timeout_s = timeout_s

    def recent(self, window_ms: int) -> Sequence[Signal]:
        _log.warning("monitoring_signal_source_stub", window_ms=window_ms,
                     note="returning no correlated signals — not yet wired")
        return ()
