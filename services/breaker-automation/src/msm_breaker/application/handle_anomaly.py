from __future__ import annotations
from msm_breaker.domain import AnomalyEvent, should_trip
from .ports import KillSwitchWriter


class HandleAnomaly:
    """Use case — PRD §5 automated circuit breaker."""

    def __init__(self, writer: KillSwitchWriter) -> None:
        self._writer = writer

    def execute(self, event: AnomalyEvent) -> bool:
        decision = should_trip(event)
        if decision.trip:
            self._writer.engage(decision.reason)
        return decision.trip
