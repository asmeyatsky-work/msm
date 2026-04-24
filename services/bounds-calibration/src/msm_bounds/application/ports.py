from __future__ import annotations
from typing import Protocol
from msm_bounds.domain import PercentileSample, ProposedBounds


class PercentileSource(Protocol):
    def sample(self, lookback_hours: int) -> PercentileSample: ...


class PullRequestGateway(Protocol):
    def open_bounds_pr(self, proposed: ProposedBounds, current_min: float, current_max: float) -> str:
        """Opens a PR updating runtime config; returns PR URL."""
