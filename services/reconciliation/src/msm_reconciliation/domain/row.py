"""Immutable reconciliation row. Mirrors the Rust/TS domain types."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class PredictionSource(str, Enum):
    MODEL = "MODEL"
    FALLBACK_TCPA = "FALLBACK_TCPA"
    FALLBACK_DATA_LAYER = "FALLBACK_DATA_LAYER"
    KILL_SWITCH = "KILL_SWITCH"


@dataclass(frozen=True, slots=True)
class ReconciliationRow:
    click_id: str
    predicted_rpc: float
    realized_rpc: float
    source: PredictionSource
    window_ends_at_ms: int

    def __post_init__(self) -> None:
        if not self.click_id:
            raise ValueError("click_id required")
        if self.predicted_rpc < 0 or self.realized_rpc < 0:
            raise ValueError("rpc must be non-negative")
        if self.window_ends_at_ms < 0:
            raise ValueError("window_ends_at_ms must be non-negative")

    @property
    def residual(self) -> float:
        return self.realized_rpc - self.predicted_rpc

    def is_complete(self, now_ms: int) -> bool:
        return now_ms >= self.window_ends_at_ms
