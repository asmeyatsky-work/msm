from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PredictionEnvelope:
    """Immutable record pushed to the activation channel."""
    click_id: str
    correlation_id: str
    predicted_rpc: float
    source: str
    model_version: str

    def __post_init__(self) -> None:
        if not self.click_id:
            raise ValueError("click_id required")
        if self.predicted_rpc < 0 or self.predicted_rpc != self.predicted_rpc:
            raise ValueError(f"predicted_rpc invalid: {self.predicted_rpc}")
