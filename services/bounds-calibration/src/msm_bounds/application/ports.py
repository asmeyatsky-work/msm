from __future__ import annotations
from typing import Protocol, Sequence
from msm_bounds.domain import BoundsAssessment, PercentileSample, ProposedBounds


class PercentileSource(Protocol):
    def sample(self, lookback_hours: int) -> PercentileSample: ...


class PullRequestGateway(Protocol):
    def open_bounds_pr(self, proposed: ProposedBounds, current_min: float, current_max: float) -> str:
        """Opens a PR updating runtime config; returns PR URL."""


class DistributionHistory(Protocol):
    """Read-only context for the agent: recent percentile samples bucketed over
    time, so it can tell a sustained shift from a single-bucket spike."""
    def recent_samples(self, lookback_hours: int, buckets: int) -> Sequence[PercentileSample]: ...


class ReviewedPullRequestGateway(Protocol):
    """PR gateway that carries the agent-authored title/rationale onto the PR.
    Called only by the deterministic use case after a BoundsAssessment validates
    (§4) — never directly by the LLM."""
    def open_reviewed_pr(
        self, proposed: ProposedBounds, current_min: float, current_max: float,
        title: str, rationale: str,
    ) -> str: ...
