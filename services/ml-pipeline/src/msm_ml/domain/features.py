"""Feature vector value object. Immutable (§3.3); invariants in __init__ (§3.4)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping

FeatureName = str


@dataclass(frozen=True, slots=True)
class FeatureVector:
    """Feature vector matching PRD §3.1. Immutable."""
    click_id: str
    device: str
    geo: str
    hour_of_day: int
    cerberus_score: float
    rpc_7d: float
    rpc_14d: float
    rpc_30d: float
    is_payday_week: bool
    auction_pressure: float
    visits_prev_30d: int

    def __post_init__(self) -> None:
        if not self.click_id:
            raise ValueError("click_id required")
        if not 0 <= self.hour_of_day <= 23:
            raise ValueError(f"hour_of_day out of range: {self.hour_of_day}")
        if not 0.0 <= self.cerberus_score <= 1.0:
            raise ValueError(f"cerberus_score out of range: {self.cerberus_score}")
        for name, v in (("rpc_7d", self.rpc_7d), ("rpc_14d", self.rpc_14d), ("rpc_30d", self.rpc_30d)):
            if v < 0 or v != v:  # reject negative or NaN
                raise ValueError(f"{name} invalid: {v}")

    def as_map(self) -> Mapping[str, float | int | bool | str]:
        return {
            "device": self.device, "geo": self.geo, "hour_of_day": self.hour_of_day,
            "cerberus_score": self.cerberus_score, "rpc_7d": self.rpc_7d,
            "rpc_14d": self.rpc_14d, "rpc_30d": self.rpc_30d,
            "is_payday_week": self.is_payday_week,
            "auction_pressure": self.auction_pressure,
            "visits_prev_30d": self.visits_prev_30d,
        }
