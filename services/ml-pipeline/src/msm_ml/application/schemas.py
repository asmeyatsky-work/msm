"""Agent I/O schema (§4, reject by default). Layer: application.
`DriftTriageOutput` is the forced structured output of the drift decider agent;
`to_domain()` maps it through the domain invariants before any retrain/alert.
"""
from __future__ import annotations
from pydantic import BaseModel, Field

from msm_ml.domain import DriftAction, DriftTriage, DriftVerdict


class DriftTriageOutput(BaseModel):
    action: DriftAction
    severity: DriftVerdict
    drivers: list[str] = Field(default_factory=list, description="Feature names driving the drift.")
    retrain_lookback_days: int = Field(default=0, ge=0, le=365)
    justification: str = Field(min_length=1)

    def to_domain(self) -> DriftTriage:
        return DriftTriage(
            action=self.action,
            severity=self.severity,
            drivers=tuple(self.drivers),
            retrain_lookback_days=self.retrain_lookback_days,
            justification=self.justification,
        )
