"""TreeSHAP explainer backed by an xgboost booster. §3.1: no decisions here."""
from __future__ import annotations
from typing import Sequence
import io

import numpy as np
import shap
import xgboost as xgb

from msm_ml.domain import FeatureVector, Attribution
from msm_ml.application import Explainer
from .xgboost_trainer import _FEATURE_ORDER, _row_to_vec


class ShapExplainer(Explainer):
    def __init__(self, booster_bytes: bytes) -> None:
        model = xgb.XGBRegressor()
        model.load_model(io.BytesIO(booster_bytes))
        self._model = model
        self._explainer = shap.TreeExplainer(model)

    def explain(self, features: Sequence[FeatureVector]) -> Sequence[Attribution]:
        X = np.stack([_row_to_vec(fv) for fv in features])
        values = self._explainer.shap_values(X)
        expected = float(self._explainer.expected_value)
        out: list[Attribution] = []
        for row in np.atleast_2d(values):
            out.append(Attribution(
                base_value=expected,
                contributions={name: float(v) for name, v in zip(_FEATURE_ORDER, row, strict=True)},
            ))
        return out
