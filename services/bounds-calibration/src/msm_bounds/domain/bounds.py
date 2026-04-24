"""Pure calibration rule: propose new min/max bounds from percentile samples.

Policy (auditable here, not buried in a query):
- lower = max(p1 of model predictions, 0.01)   — reject near-zero outliers
- upper = p99 * safety_multiplier               — absorb short spikes
- Never propose a change smaller than `min_change_ratio` — avoid churn.
- Reject samples if `n` is too small to be statistically meaningful.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PercentileSample:
    p1: float
    p99: float
    n: int

    def __post_init__(self) -> None:
        if self.p1 < 0 or self.p99 < 0:
            raise ValueError("percentiles must be non-negative")
        if self.p1 > self.p99:
            raise ValueError("p1 cannot exceed p99")
        if self.n < 0:
            raise ValueError("n must be non-negative")


@dataclass(frozen=True, slots=True)
class ProposedBounds:
    min_rpc: float
    max_rpc: float
    reason: str

    def __post_init__(self) -> None:
        if self.min_rpc < 0 or self.max_rpc <= 0:
            raise ValueError("bounds must be positive")
        if self.min_rpc > self.max_rpc:
            raise ValueError("min > max")


def propose_bounds(
    sample: PercentileSample,
    current_min: float,
    current_max: float,
    *,
    floor_min: float = 0.01,
    safety_multiplier: float = 1.5,
    min_sample_size: int = 10_000,
    min_change_ratio: float = 0.10,
) -> ProposedBounds | None:
    """Return `None` when no change is warranted."""
    if sample.n < min_sample_size:
        return None

    new_min = max(sample.p1, floor_min)
    new_max = sample.p99 * safety_multiplier
    if new_max <= new_min:
        return None

    min_delta = abs(new_min - current_min) / max(current_min, 1e-9)
    max_delta = abs(new_max - current_max) / max(current_max, 1e-9)
    if min_delta < min_change_ratio and max_delta < min_change_ratio:
        return None

    return ProposedBounds(
        min_rpc=round(new_min, 4),
        max_rpc=round(new_max, 4),
        reason=f"n={sample.n}, p1={sample.p1:.4f}, p99={sample.p99:.4f}",
    )
