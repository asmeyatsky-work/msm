from __future__ import annotations
from typing import Protocol, Sequence
from msm_ml.domain import FeatureVector, Attribution


class Explainer(Protocol):
    def explain(self, features: Sequence[FeatureVector]) -> Sequence[Attribution]: ...


class ExplainModel:
    """Use case: produce SHAP attributions for a batch of click feature vectors.
    Intended for offline analysis and /v1/explain requests (rate-limited)."""

    def __init__(self, explainer: Explainer) -> None:
        self._explainer = explainer

    def execute(self, features: Sequence[FeatureVector]) -> Sequence[Attribution]:
        if not features:
            return []
        return self._explainer.explain(features)
