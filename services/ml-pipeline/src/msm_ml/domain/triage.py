"""Pure drift-triage value objects. Layer: domain. Imports no SDK (§2).

`detect_drift` + `DriftScore.verdict()` stay deterministic (ADR 0005). This
models the *judgment* an LLM agent adds — given per-feature PSI, what to DO:
retrain, alert, or nothing — as an immutable, self-checking value object.
Constructing it is the §4 gate before the high-blast-radius retrain write.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .drift import DriftVerdict


class DriftAction(str, Enum):
    RETRAIN = "retrain"  # high blast radius — trains + registers a new model
    ALERT = "alert"      # surface to humans, do not retrain
    NOOP = "noop"        # acknowledged, no action


_MAX_LOOKBACK_DAYS = 365


@dataclass(frozen=True, slots=True)
class DriftTriage:
    action: DriftAction
    severity: DriftVerdict
    drivers: tuple[str, ...]          # feature names driving the drift
    retrain_lookback_days: int        # >0 only for RETRAIN
    justification: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, DriftAction):
            raise ValueError("action must be a DriftAction")
        if not isinstance(self.severity, DriftVerdict):
            raise ValueError("severity must be a DriftVerdict")
        if not self.justification.strip():
            raise ValueError("justification required")
        if self.action is DriftAction.RETRAIN:
            if not self.drivers:
                raise ValueError("RETRAIN requires at least one driver feature")
            if not 1 <= self.retrain_lookback_days <= _MAX_LOOKBACK_DAYS:
                raise ValueError(f"retrain_lookback_days must be in [1, {_MAX_LOOKBACK_DAYS}]")
        elif self.action is DriftAction.ALERT:
            if not self.drivers:
                raise ValueError("ALERT requires at least one driver feature")
            if self.retrain_lookback_days != 0:
                raise ValueError("retrain_lookback_days must be 0 unless RETRAIN")
        else:  # NOOP
            if self.retrain_lookback_days != 0:
                raise ValueError("retrain_lookback_days must be 0 unless RETRAIN")
