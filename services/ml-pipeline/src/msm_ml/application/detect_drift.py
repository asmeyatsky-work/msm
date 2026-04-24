from __future__ import annotations
from typing import Sequence
from msm_ml.domain import DriftScore, DriftVerdict
from .ports import DriftMonitor


class DetectDrift:
    """Wraps the drift monitor port; PRD §5 feature drift alarms feed from here."""

    def __init__(self, monitor: DriftMonitor) -> None:
        self._monitor = monitor

    def execute(self, baseline_window_ms: int, current_window_ms: int) -> tuple[DriftVerdict, Sequence[DriftScore]]:
        scores = list(self._monitor.score(baseline_window_ms, current_window_ms))
        worst = DriftVerdict.HEALTHY
        for s in scores:
            v = s.verdict()
            if v == DriftVerdict.BREACH:
                worst = DriftVerdict.BREACH
                break
            if v == DriftVerdict.WARN and worst != DriftVerdict.BREACH:
                worst = DriftVerdict.WARN
        return worst, scores
