from __future__ import annotations
from dataclasses import dataclass
from msm_ml.domain import ModelVersion
from .ports import FeatureRepo, ModelTrainer, ModelRegistry


@dataclass(frozen=True, slots=True)
class TrainModelResult:
    model_version: ModelVersion
    n_rows: int


class TrainModel:
    """Use case — PRD §3 training loop. Independent steps (data, train, register)
    are sequential by data dependency, so no DAG split (§3.6 allows this)."""

    def __init__(self, features: FeatureRepo, trainer: ModelTrainer, registry: ModelRegistry) -> None:
        self._features = features
        self._trainer = trainer
        self._registry = registry

    def execute(self, model_id: str, window_start_ms: int, window_end_ms: int) -> TrainModelResult:
        rows = list(self._features.load_training_frame(window_start_ms, window_end_ms))
        if not rows:
            raise ValueError("no training rows in window")
        artifact = self._trainer.train(rows)
        version = self._registry.register(artifact, model_id)
        return TrainModelResult(model_version=version, n_rows=len(rows))
