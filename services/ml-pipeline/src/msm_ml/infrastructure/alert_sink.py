"""AlertSink adapters. Layer: infrastructure. Implements application.AlertSink.
§4/§6: structured, no PII; every emit is observable.

`InMemoryAlertSink` for tests; `LogAlertSink` emits a structured drift-alert log
line (picked up by the monitoring/alerting stack). A Pub/Sub or paging adapter
can replace it without touching the use case.
"""
from __future__ import annotations

import structlog

from msm_ml.application.ports import AlertSink
from msm_ml.domain import DriftTriage

_log = structlog.get_logger()


class InMemoryAlertSink(AlertSink):
    def __init__(self) -> None:
        self.emitted: list[DriftTriage] = []

    def emit(self, triage: DriftTriage) -> None:
        self.emitted.append(triage)


class LogAlertSink(AlertSink):
    def emit(self, triage: DriftTriage) -> None:
        _log.warning(
            "drift_alert",
            severity=triage.severity.value,
            drivers=list(triage.drivers),
            justification=triage.justification,
        )
