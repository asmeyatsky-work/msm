"""SHAP attribution value object. Pure domain."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Attribution:
    """Per-feature SHAP contribution for a single prediction.
    `base_value + sum(contributions.values())` ≈ predicted RPC (XGBoost TreeSHAP invariant)."""
    base_value: float
    contributions: Mapping[str, float]

    def __post_init__(self) -> None:
        if self.base_value != self.base_value:  # NaN
            raise ValueError("base_value NaN")
        for k, v in self.contributions.items():
            if not k:
                raise ValueError("empty feature name")
            if v != v:
                raise ValueError(f"contribution NaN for {k}")

    def top_features(self, k: int) -> list[tuple[str, float]]:
        if k < 0:
            raise ValueError("k must be non-negative")
        return sorted(self.contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:k]
