"""Use case: dispatch a *validated* triage decision. Layer: application.
Ports: IncidentNotifier. MCP: none.

This is the deterministic half of the breaker triage flow. The LLM agent
produces a `TriageDecision` (already schema-validated, ADR 0005 §4); this use
case performs the escalation write. Keeping the write here — not in the agent —
means the side effect is unit-testable with zero mocks of the LLM and cannot
fire on un-validated output. Mirrors the existing `HandleAnomaly` shape.
"""
from __future__ import annotations

from msm_breaker.domain import AnomalyEvent, EscalationAction, TriageDecision
from .ports import IncidentNotifier


class TriageAnomaly:
    def __init__(self, notifier: IncidentNotifier) -> None:
        self._notifier = notifier

    def execute(self, event: AnomalyEvent, decision: TriageDecision) -> TriageDecision:
        # `decision` is already validated by its constructor. Dispatch by action.
        if not decision.escalate:
            return decision
        if decision.action is EscalationAction.PAGE_ONCALL:
            self._notifier.page(decision, event)
        elif decision.action is EscalationAction.ANNOTATE:
            self._notifier.annotate(decision, event)
        return decision
