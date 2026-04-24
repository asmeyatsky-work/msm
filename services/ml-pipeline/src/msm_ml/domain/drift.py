"""Feature drift — PRD §5 Anomaly Detection. Pure domain rule."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class DriftVerdict(str, Enum):
    HEALTHY = "healthy"
    WARN = "warn"
    BREACH = "breach"


@dataclass(frozen=True, slots=True)
class DriftScore:
    feature_name: str
    psi: float  # Population Stability Index

    def __post_init__(self) -> None:
        if self.psi < 0 or self.psi != self.psi:
            raise ValueError(f"psi invalid: {self.psi}")

    def verdict(self) -> DriftVerdict:
        # Standard PSI thresholds.
        if self.psi < 0.1:
            return DriftVerdict.HEALTHY
        if self.psi < 0.25:
            return DriftVerdict.WARN
        return DriftVerdict.BREACH
