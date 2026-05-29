"""Deterministic triage tests (§5 track, ADR 0006). No LLM here — the agent's
reasoning is covered by the eval track (test_triage_eval.py). These cover the
schema gate, the domain invariants, and the escalation dispatch."""
import pytest

from msm_breaker.domain import (
    AnomalyEvent, AnomalyKind, EscalationAction, Severity, Signal, TriageDecision,
)
from msm_breaker.application import TriageAnomaly, TriageOutput
from msm_breaker.application.triage_agent import _breaker_verdict


class _Notifier:
    def __init__(self):
        self.paged = []
        self.annotated = []

    def page(self, decision, event):
        self.paged.append((decision, event))
        return "incident://paged"

    def annotate(self, decision, event):
        self.annotated.append((decision, event))
        return "incident://annotated"


def _event(kind=AnomalyKind.NULL_OR_ZERO_RATE):
    return AnomalyEvent(kind=kind, value=0.04, threshold=0.03, occurred_at_ms=1)


# --- domain invariants ---------------------------------------------------------

def test_escalate_true_requires_non_none_action():
    with pytest.raises(ValueError):
        TriageDecision(True, Severity.SEV1, EscalationAction.NONE, "cause", "why")


def test_escalate_false_requires_none_action():
    with pytest.raises(ValueError):
        TriageDecision(False, Severity.SEV3, EscalationAction.ANNOTATE, "cause", "why")


@pytest.mark.parametrize("cause,why", [("", "why"), ("cause", "  ")])
def test_blank_text_rejected(cause, why):
    with pytest.raises(ValueError):
        TriageDecision(True, Severity.SEV2, EscalationAction.PAGE_ONCALL, cause, why)


def test_signal_rejects_blank_name():
    with pytest.raises(ValueError):
        Signal(name="", value=1.0, threshold=0.5, observed_at_ms=1)


# --- schema gate ---------------------------------------------------------------

def test_triage_output_maps_to_domain():
    out = TriageOutput(escalate=True, severity=Severity.SEV1,
                       action=EscalationAction.PAGE_ONCALL,
                       cause_hypothesis="null-rate spike upstream",
                       justification="null_rate 4% > 3% sustained 5m")
    decision = out.to_domain()
    assert decision.escalate
    assert decision.action is EscalationAction.PAGE_ONCALL


def test_triage_output_invalid_combo_rejected_at_gate():
    out = TriageOutput(escalate=True, severity=Severity.SEV1,
                       action=EscalationAction.NONE,
                       cause_hypothesis="x", justification="y")
    with pytest.raises(ValueError):
        out.to_domain()


# --- escalation dispatch -------------------------------------------------------

def test_page_dispatches_page():
    n = _Notifier()
    d = TriageDecision(True, Severity.SEV1, EscalationAction.PAGE_ONCALL, "c", "j")
    TriageAnomaly(n).execute(_event(), d)
    assert len(n.paged) == 1 and not n.annotated


def test_annotate_dispatches_annotate():
    n = _Notifier()
    d = TriageDecision(True, Severity.SEV2, EscalationAction.ANNOTATE, "c", "j")
    TriageAnomaly(n).execute(_event(), d)
    assert len(n.annotated) == 1 and not n.paged


def test_no_escalation_is_noop():
    n = _Notifier()
    d = TriageDecision(False, Severity.SEV3, EscalationAction.NONE, "c", "j")
    TriageAnomaly(n).execute(_event(), d)
    assert not n.paged and not n.annotated


# --- verdict tool (pure) -------------------------------------------------------

def test_breaker_verdict_tool_reports_trip():
    v = _breaker_verdict("null_or_zero_rate", 0.04, 0.03, 1)
    assert v["trip"] is True and v["breached"] is True


def test_breaker_verdict_tool_reports_no_trip():
    v = _breaker_verdict("latency", 0.5, 1.0, 1)
    assert v["trip"] is False and v["breached"] is False
