"""Pure bounds-assessment value objects. Layer: domain. Ports: none. MCP: none.

The bounds *math* lives in `bounds.py:propose_bounds` and stays fully
deterministic (ADR 0005). This module models the *judgment* an LLM agent adds on
top — is a proposed change a genuine distribution shift worth a PR, or a
transient spike / data-quality artefact to skip — as an immutable, self-checking
value object. Constructing it IS the §4 gate before any PR write.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class ChangeClass(str, Enum):
    GENUINE_SHIFT = "genuine_shift"      # sustained, real — open a PR
    TRANSIENT_SPIKE = "transient_spike"  # short-lived — do not churn bounds
    DATA_QUALITY = "data_quality"        # nulls/sparse/suspect input — do not act
    NO_CHANGE = "no_change"              # candidate not materially different


@dataclass(frozen=True, slots=True)
class BoundsAssessment:
    """Validated agent decision about whether to act on a proposed bounds change.

    Policy encoded as invariants (§3.4): only a GENUINE_SHIFT may open a PR; any
    non-opening decision must carry a non-genuine class explaining the skip."""
    open_pr: bool
    change_class: ChangeClass
    confidence: float
    pr_title: str
    rationale: str        # reviewer-facing PR body authored by the agent
    justification: str    # why this class / decision (always required)

    def __post_init__(self) -> None:
        if not isinstance(self.change_class, ChangeClass):
            raise ValueError("change_class must be a ChangeClass")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if not self.justification.strip():
            raise ValueError("justification required")
        if self.open_pr:
            if self.change_class is not ChangeClass.GENUINE_SHIFT:
                raise ValueError("only a GENUINE_SHIFT may open a PR")
            if not self.pr_title.strip() or not self.rationale.strip():
                raise ValueError("open_pr requires pr_title and rationale")
        elif self.change_class is ChangeClass.GENUINE_SHIFT:
            raise ValueError("a GENUINE_SHIFT must open a PR (open_pr=False inconsistent)")
