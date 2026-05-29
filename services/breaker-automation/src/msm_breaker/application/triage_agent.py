"""Breaker triage agent (ADK). Layer: application.
Ports used (as read-only tools): SignalSource, plus the pure domain
`should_trip`. MCP: none (this agent owns no MCP toolset; it has no kill-switch
tool by design — ADR 0005 §5).
Stack: Python 3.12 + google-adk on Vertex Agent Engine (ADR 0001 §1, ADR 0005).

Design (ADR 0005): the LLM reasons, the domain decides. The agent has ONLY
read tools. It never trips the breaker and never escalates directly — it emits a
validated `TriageOutput`; the deterministic `TriageAnomaly` use case performs the
escalation write.

ADK note: an LlmAgent with `output_schema` set cannot also use tools, so this is
a SequentialAgent of two sub-agents:
  1. investigator — has the read tools, gathers evidence into session state.
  2. decider     — no tools, `output_schema=TriageOutput`, emits the decision.

ADK imports are deferred into the builder so the package imports without
google-adk present (domain + use-case unit tests need no model SDK).
"""
from __future__ import annotations
import os
from typing import Any

from msm_breaker.domain import AnomalyKind, should_trip, AnomalyEvent
from .ports import SignalSource
from .schemas import TriageOutput

_DEFAULT_MODEL = os.environ.get("TRIAGE_MODEL", "gemini-2.5-flash")

_INVESTIGATOR_INSTRUCTION = """\
You are the on-call triage investigator for an ad-revenue scoring platform's
circuit breaker. The breaker has just evaluated an anomaly. Your job is to
GATHER EVIDENCE only — do not decide escalation yet.

Steps:
1. Call `breaker_verdict` with the anomaly fields to see the deterministic trip
   decision and its reason. You do not override it; you explain around it.
2. Call `recent_signals` to pull correlated signals from the last few minutes.
3. Write a concise factual analysis: what fired, what correlates, what the most
   likely cause is, and how customer-impacting it looks. Do not invent signals.
"""

_DECIDER_INSTRUCTION = """\
You are the triage decider. Using ONLY the investigator's analysis in the
conversation, output a single triage decision as structured JSON matching the
schema. Rules:
- escalate=false MUST use action="none".
- escalate=true MUST use a non-"none" action ("page_oncall" or "annotate").
- Reserve "page_oncall"/sev1 for customer-impacting or sustained breaches;
  prefer "annotate"/sev2-3 for transient or low-impact signals.
- justification must cite the concrete signals from the analysis.
"""


def _breaker_verdict(kind: str, value: float, threshold: float, occurred_at_ms: int) -> dict[str, Any]:
    """Read-only tool: the deterministic trip verdict. Pure domain call —
    the agent sees the same answer the Cloud Function acted on."""
    event = AnomalyEvent(
        kind=AnomalyKind(kind), value=value, threshold=threshold, occurred_at_ms=occurred_at_ms,
    )
    decision = should_trip(event)
    return {"trip": decision.trip, "reason": decision.reason, "breached": event.breached()}


def build_triage_agent(signal_source: SignalSource, model: str = _DEFAULT_MODEL,
                       after_model_callback=None):
    """Construct the SequentialAgent. Returns an ADK agent ready for Runner /
    Vertex Agent Engine deployment.

    `after_model_callback` is injected (not imported) to keep §2 layering: the
    §6 AI-call observability callback lives in infrastructure and is wired in by
    presentation (ADR 0007)."""
    from google.adk.agents import LlmAgent, SequentialAgent  # deferred import

    def recent_signals(window_ms: int) -> list[dict[str, Any]]:
        """Read-only tool: correlated signals in the trailing window."""
        return [
            {"name": s.name, "value": s.value, "threshold": s.threshold,
             "observed_at_ms": s.observed_at_ms}
            for s in signal_source.recent(window_ms)
        ]

    investigator = LlmAgent(
        name="breaker_triage_investigator",
        model=model,
        instruction=_INVESTIGATOR_INSTRUCTION,
        tools=[_breaker_verdict, recent_signals],
        output_key="analysis",
        after_model_callback=after_model_callback,
    )
    decider = LlmAgent(
        name="breaker_triage_decider",
        model=model,
        instruction=_DECIDER_INSTRUCTION,
        output_schema=TriageOutput,
        output_key="triage",
        after_model_callback=after_model_callback,
    )
    return SequentialAgent(
        name="breaker_triage",
        sub_agents=[investigator, decider],
    )
