"""Breaker triage agent entrypoint. Layer: presentation.
Stack: Python 3.12 + google-adk on Vertex Agent Engine (ADR 0005).

Wires concrete infrastructure adapters to the application agent + use case, and
exposes `root_agent` for `adk deploy` / Agent Engine. The triage agent does NOT
replace the deterministic Cloud Function trip path in `function.py`; it runs
after a trip to produce escalation decisions (ADR 0005 §5).

This is the one place allowed to import both application and infrastructure (§2),
so it injects the §6 AI-call callback into the agent here (ADR 0007).
"""
from __future__ import annotations
import json
import os

from msm_breaker.application import TriageAnomaly, TriageOutput
from msm_breaker.application.triage_agent import build_triage_agent
from msm_breaker.domain import AnomalyEvent
from msm_breaker.infrastructure.ai_call_log import after_model_callback
from msm_breaker.infrastructure.incident_notifier import PubSubIncidentNotifier
from msm_breaker.infrastructure.signal_source import MonitoringSignalSource

_PROJECT = os.environ.get("GCP_PROJECT", "")
_INCIDENT_TOPIC = os.environ.get("INCIDENT_TOPIC", "breaker-incidents")

_signal_source = MonitoringSignalSource(_PROJECT)
_notifier = PubSubIncidentNotifier(_PROJECT, _INCIDENT_TOPIC)

# Module-level agent for Vertex Agent Engine to discover.
root_agent = build_triage_agent(_signal_source, after_model_callback=after_model_callback)

_triage = TriageAnomaly(_notifier)


async def run_triage(event: AnomalyEvent) -> TriageOutput:
    """Run the triage agent for one anomaly and dispatch the escalation.

    Returns the validated decision. The schema gate (§4) is `TriageOutput`
    validation + `to_domain()`; the escalation write happens in `TriageAnomaly`.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="breaker-triage",
                    session_service=session_service)
    await session_service.create_session(
        app_name="breaker-triage", user_id="breaker", session_id=str(event.occurred_at_ms),
    )
    prompt = types.Content(role="user", parts=[types.Part(text=json.dumps({
        "kind": event.kind.value, "value": event.value,
        "threshold": event.threshold, "occurred_at_ms": event.occurred_at_ms,
    }))])

    final = None
    async for ev in runner.run_async(user_id="breaker", session_id=str(event.occurred_at_ms),
                                     new_message=prompt):
        if ev.is_final_response():
            final = ev

    session = await session_service.get_session(
        app_name="breaker-triage", user_id="breaker", session_id=str(event.occurred_at_ms),
    )
    raw = session.state.get("triage")
    output = TriageOutput.model_validate(raw if isinstance(raw, dict)
                                         else json.loads(raw))
    decision = output.to_domain()  # §4 gate — raises before any write
    _triage.execute(event, decision)
    return output
