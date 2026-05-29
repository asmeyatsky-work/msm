"""Pure triage value objects. Layer: domain. Ports: none. MCP: none.

The breaker *trip* decision lives in `decision.py` and stays fully
deterministic (ADR 0005). This module models the *post-trip triage* outcome —
the judgment an LLM agent produces — as an immutable, self-validating value
object so that no escalation side effect can fire on un-validated AI output
(§4). Invariants are enforced in the constructor, never via setters (§3.4).
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    SEV1 = "sev1"  # customer-impacting, immediate
    SEV2 = "sev2"  # degraded, needs attention this shift
    SEV3 = "sev3"  # informational / track-only


class EscalationAction(str, Enum):
    PAGE_ONCALL = "page_oncall"
    ANNOTATE = "annotate"        # record on the incident timeline, no page
    NONE = "none"                # no escalation warranted


@dataclass(frozen=True, slots=True)
class Signal:
    """One correlated observation the agent reasons over (read-only evidence)."""
    name: str
    value: float
    threshold: float
    observed_at_ms: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("signal name required")
        if self.observed_at_ms < 0:
            raise ValueError("observed_at_ms must be non-negative")


@dataclass(frozen=True, slots=True)
class TriageDecision:
    """Validated triage outcome. Constructing this IS the §4 schema gate that
    must succeed before any escalation write happens."""
    escalate: bool
    severity: Severity
    action: EscalationAction
    cause_hypothesis: str
    justification: str

    def __post_init__(self) -> None:
        if not isinstance(self.severity, Severity):
            raise ValueError("severity must be a Severity")
        if not isinstance(self.action, EscalationAction):
            raise ValueError("action must be an EscalationAction")
        if not self.cause_hypothesis.strip():
            raise ValueError("cause_hypothesis required")
        if not self.justification.strip():
            raise ValueError("justification required")
        if self.escalate and self.action is EscalationAction.NONE:
            raise ValueError("escalate=True requires a non-NONE action")
        if not self.escalate and self.action is not EscalationAction.NONE:
            raise ValueError("escalate=False requires action=NONE")
