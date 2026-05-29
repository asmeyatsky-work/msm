"""Use case: act on a *validated* bounds assessment. Layer: application.
Ports: ReviewedPullRequestGateway. MCP: none.

The deterministic half of the agent-driven calibration flow. The canonical
`ProposedBounds` are computed deterministically (presentation runs
`propose_bounds`); this use case only opens the PR when the agent's validated
assessment says so — and passes the deterministic numbers, never any number the
LLM produced. Mirrors `Calibrate`, which remains the non-agent path.
"""
from __future__ import annotations
from dataclasses import dataclass

from msm_bounds.domain import BoundsAssessment, ChangeClass, ProposedBounds
from .ports import ReviewedPullRequestGateway


@dataclass(frozen=True, slots=True)
class AssessResult:
    pr_url: str | None
    reason: str
    change_class: ChangeClass


class AssessBounds:
    def __init__(self, gateway: ReviewedPullRequestGateway) -> None:
        self._gateway = gateway

    def execute(
        self, proposed: ProposedBounds, current_min: float, current_max: float,
        assessment: BoundsAssessment,
    ) -> AssessResult:
        if not assessment.open_pr:
            return AssessResult(None, assessment.justification, assessment.change_class)
        url = self._gateway.open_reviewed_pr(
            proposed, current_min, current_max, assessment.pr_title, assessment.rationale,
        )
        return AssessResult(url, assessment.rationale, assessment.change_class)
