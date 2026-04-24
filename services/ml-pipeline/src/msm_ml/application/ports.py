"""Ports (§3.2): every external dependency is an interface implemented in infrastructure."""
from __future__ import annotations
from typing import Protocol, Sequence
from msm_ml.domain import FeatureVector, ModelVersion, DriftScore


class FeatureRepo(Protocol):
    def load_training_frame(self, start_ms: int, end_ms: int) -> Sequence[tuple[FeatureVector, float]]:
        """Yields (features, target_revenue) rows for the conversion window."""


class ModelTrainer(Protocol):
    def train(self, rows: Sequence[tuple[FeatureVector, float]]) -> bytes:
        """Returns serialized XGBoost booster."""


class ModelRegistry(Protocol):
    def register(self, artifact: bytes, model_id: str) -> ModelVersion: ...
    def latest(self, model_id: str) -> ModelVersion | None: ...


class DriftMonitor(Protocol):
    def score(self, baseline_window_ms: int, current_window_ms: int) -> Sequence[DriftScore]: ...
