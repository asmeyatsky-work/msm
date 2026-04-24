from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelVersion:
    """Immutable identifier for a registered model version."""
    model_id: str
    version: str
    trained_at_epoch_ms: int

    def __post_init__(self) -> None:
        if not self.model_id or not self.version:
            raise ValueError("model_id and version required")
        if self.trained_at_epoch_ms < 0:
            raise ValueError("trained_at_epoch_ms must be non-negative")

    def qualified(self) -> str:
        return f"{self.model_id}@{self.version}"
