"""Use case: act on a *validated* drift triage. Layer: application.
Ports: TrainModel (retrain), AlertSink (alert). MCP: none.

The deterministic half of the agent-driven drift flow. The agent produces a
DriftTriage (schema-validated, §4); this use case performs the side effect.
RETRAIN is the highest-blast-radius action — it is executed here by the existing
deterministic TrainModel use case, never by the LLM. The retrain window is
derived from the agent's lookback (already clamped to [1, 365] in the domain).
"""
from __future__ import annotations
from dataclasses import dataclass

from msm_ml.domain import DriftAction, DriftTriage, ModelVersion
from .ports import AlertSink, Trainer

_MS_PER_DAY = 86_400_000


@dataclass(frozen=True, slots=True)
class TriageDispatch:
    action: DriftAction
    model_version: ModelVersion | None
    detail: str


class TriageDrift:
    def __init__(self, train: Trainer, alert: AlertSink) -> None:
        self._train = train
        self._alert = alert

    def execute(self, model_id: str, triage: DriftTriage, now_ms: int) -> TriageDispatch:
        if triage.action is DriftAction.RETRAIN:
            start_ms = now_ms - triage.retrain_lookback_days * _MS_PER_DAY
            result = self._train.execute(model_id, start_ms, now_ms)
            return TriageDispatch(
                DriftAction.RETRAIN, result.model_version,
                f"retrained on {triage.retrain_lookback_days}d window ({result.n_rows} rows)",
            )
        if triage.action is DriftAction.ALERT:
            self._alert.emit(triage)
            return TriageDispatch(DriftAction.ALERT, None, triage.justification)
        return TriageDispatch(DriftAction.NOOP, None, triage.justification)
