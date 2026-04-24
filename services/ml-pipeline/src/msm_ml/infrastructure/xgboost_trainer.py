"""XGBoost trainer — PRD §3. Real fit; returns a booster buffer."""
from __future__ import annotations
from typing import Sequence
import io

import numpy as np
import xgboost as xgb

from msm_ml.domain import FeatureVector
from msm_ml.application.ports import ModelTrainer

# Feature order is fixed at training; scoring-api must use the same order.
_FEATURE_ORDER: tuple[str, ...] = (
    "hour_of_day", "cerberus_score", "rpc_7d", "rpc_14d", "rpc_30d",
    "is_payday_week", "auction_pressure", "visits_prev_30d",
)


def _row_to_vec(fv: FeatureVector) -> np.ndarray:
    m = fv.as_map()
    return np.array([float(m[k]) for k in _FEATURE_ORDER], dtype=np.float32)


class XGBoostTrainer(ModelTrainer):
    def __init__(self, *, max_depth: int = 6, n_estimators: int = 400,
                 learning_rate: float = 0.05, objective: str = "reg:squarederror") -> None:
        self._params = {
            "max_depth": max_depth,
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "objective": objective,
            "tree_method": "hist",
        }

    def train(self, rows: Sequence[tuple[FeatureVector, float]]) -> bytes:
        if not rows:
            raise ValueError("no rows to train on")
        X = np.stack([_row_to_vec(fv) for fv, _ in rows])
        y = np.array([t for _, t in rows], dtype=np.float32)
        model = xgb.XGBRegressor(**self._params)
        model.fit(X, y)
        buf = io.BytesIO()
        model.save_model(buf)  # JSON-encoded booster; portable across xgboost versions
        return buf.getvalue()

    @staticmethod
    def feature_order() -> tuple[str, ...]:
        return _FEATURE_ORDER
