from __future__ import annotations
from dataclasses import dataclass
from msm_bounds.domain import propose_bounds
from .ports import PercentileSource, PullRequestGateway


@dataclass(frozen=True, slots=True)
class CalibrateResult:
    pr_url: str | None
    reason: str


class Calibrate:
    """Use case. The decision (propose or not) lives in domain; this layer
    coordinates source → policy → PR."""

    def __init__(self, source: PercentileSource, gateway: PullRequestGateway) -> None:
        self._source = source
        self._gateway = gateway

    def execute(self, lookback_hours: int, current_min: float, current_max: float) -> CalibrateResult:
        sample = self._source.sample(lookback_hours)
        proposed = propose_bounds(sample, current_min, current_max)
        if proposed is None:
            return CalibrateResult(pr_url=None, reason="no change warranted")
        pr_url = self._gateway.open_bounds_pr(proposed, current_min, current_max)
        return CalibrateResult(pr_url=pr_url, reason=proposed.reason)
