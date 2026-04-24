from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class AnomalyKind(str, Enum):
    NULL_OR_ZERO_RATE = "null_or_zero_rate"   # PRD §5: >3% triggers the breaker
    FEATURE_DRIFT = "feature_drift"
    LATENCY = "latency"


@dataclass(frozen=True, slots=True)
class AnomalyEvent:
    kind: AnomalyKind
    value: float
    threshold: float
    occurred_at_ms: int

    def __post_init__(self) -> None:
        if self.value < 0 or self.threshold < 0:
            raise ValueError("value and threshold must be non-negative")
        if self.occurred_at_ms < 0:
            raise ValueError("occurred_at_ms must be non-negative")

    def breached(self) -> bool:
        return self.value > self.threshold
