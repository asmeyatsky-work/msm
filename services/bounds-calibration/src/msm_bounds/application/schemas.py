"""Agent I/O schema (§4, reject by default). Layer: application.
`BoundsAssessmentOutput` is the forced structured output of the bounds decider
agent; `to_domain()` maps it through the domain invariants before any PR write.
"""
from __future__ import annotations
from pydantic import BaseModel, Field

from msm_bounds.domain import BoundsAssessment, ChangeClass


class BoundsAssessmentOutput(BaseModel):
    open_pr: bool = Field(description="Whether to open a recalibration PR.")
    change_class: ChangeClass
    confidence: float = Field(ge=0.0, le=1.0)
    pr_title: str = Field(default="", description="PR title (required iff open_pr).")
    rationale: str = Field(default="", description="Reviewer-facing PR body (required iff open_pr).")
    justification: str = Field(min_length=1, description="Why this class/decision.")

    def to_domain(self) -> BoundsAssessment:
        return BoundsAssessment(
            open_pr=self.open_pr,
            change_class=self.change_class,
            confidence=self.confidence,
            pr_title=self.pr_title,
            rationale=self.rationale,
            justification=self.justification,
        )
