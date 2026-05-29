"""Agent I/O schema (§4 schema-based validation, reject by default).
Layer: application. Stack: pydantic is permitted in application; the domain
stays SDK-free (import-linter `domain-purity`).

`TriageOutput` is the structured output the ADK decider agent must emit. It is
validated by ADK against this schema, then mapped to the domain `TriageDecision`
(whose constructor re-checks cross-field invariants) before any write fires.
"""
from __future__ import annotations
from pydantic import BaseModel, Field

from msm_breaker.domain import EscalationAction, Severity, TriageDecision


class TriageOutput(BaseModel):
    """Forced structured output of the triage agent."""
    escalate: bool = Field(description="Whether this incident warrants escalation.")
    severity: Severity
    action: EscalationAction
    cause_hypothesis: str = Field(min_length=1, description="Most likely root cause.")
    justification: str = Field(min_length=1, description="Evidence-backed rationale.")

    def to_domain(self) -> TriageDecision:
        """Map to the domain value object. Raises ValueError on invariant breach —
        this is the gate that stops a malformed AI decision from escalating."""
        return TriageDecision(
            escalate=self.escalate,
            severity=self.severity,
            action=self.action,
            cause_hypothesis=self.cause_hypothesis,
            justification=self.justification,
        )
