"""Ports (§3.2): every external dependency is an interface implemented in infrastructure."""
from __future__ import annotations
from typing import Protocol, Sequence
from msm_ml.domain import FeatureVector, ModelVersion, DriftScore, DriftTriage


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


class AlertSink(Protocol):
    """Surface a drift triage to humans (ALERT action). Called only by the
    deterministic TriageDrift use case after a DriftTriage validates (§4)."""
    def emit(self, triage: "DriftTriage") -> None: ...


class Trainer(Protocol):
    """Produces a new registered model version for a training window. Satisfied
    by the in-process TrainModel and by an adapter that triggers the existing
    ml-pipeline-train Cloud Run Job (returns a result with .model_version /
    .n_rows). Lets TriageDrift dispatch RETRAIN without knowing which."""
    def execute(self, model_id: str, window_start_ms: int, window_end_ms: int): ...
