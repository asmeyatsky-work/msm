"""Feature vector value object. Immutable (§3.3); invariants in __init__ (§3.4).

Schema: PRD V2 (Credit Cards) §7.1.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Optional

FeatureName = str

_INCOME_BANDS = {"low", "mid", "high"}


@dataclass(frozen=True, slots=True)
class FeatureVector:
    """Feature vector matching PRD V2 §7.1. Immutable."""
    click_id: str
    vertical_id: str
    device: str
    geo: str
    hour_of_day: int
    product_type: str
    card_product_id: str
    query_intent: str
    affinity_score: float
    prior_applicant: bool
    income_band_bucket: Optional[str]
    auction_pressure: float
    rpc_14d: float
    rpc_60d: float
    visits_prev_30d: int

    def __post_init__(self) -> None:
        if not self.click_id:
            raise ValueError("click_id required")
        if not self.vertical_id:
            raise ValueError("vertical_id required")
        if not self.product_type:
            raise ValueError("product_type required")
        if not 0 <= self.hour_of_day <= 23:
            raise ValueError(f"hour_of_day out of range: {self.hour_of_day}")
        if not 0.0 <= self.affinity_score <= 1.0:
            raise ValueError(f"affinity_score out of range: {self.affinity_score}")
        if not 0.0 <= self.auction_pressure <= 1.0:
            raise ValueError(f"auction_pressure out of range: {self.auction_pressure}")
        for name, v in (("rpc_14d", self.rpc_14d), ("rpc_60d", self.rpc_60d)):
            if v < 0 or v != v:  # reject negative or NaN
                raise ValueError(f"{name} invalid: {v}")
        if self.income_band_bucket is not None and self.income_band_bucket not in _INCOME_BANDS:
            raise ValueError(f"income_band_bucket invalid: {self.income_band_bucket}")

    def as_map(self) -> Mapping[str, float | int | bool | str | None]:
        return {
            "vertical_id": self.vertical_id,
            "device": self.device, "geo": self.geo,
            "hour_of_day": self.hour_of_day,
            "product_type": self.product_type,
            "card_product_id": self.card_product_id,
            "query_intent": self.query_intent,
            "affinity_score": self.affinity_score,
            "prior_applicant": self.prior_applicant,
            "income_band_bucket": self.income_band_bucket,
            "auction_pressure": self.auction_pressure,
            "rpc_14d": self.rpc_14d,
            "rpc_60d": self.rpc_60d,
            "visits_prev_30d": self.visits_prev_30d,
        }
