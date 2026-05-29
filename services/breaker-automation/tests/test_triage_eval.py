"""Eval track (ADR 0006) for the breaker triage agent. Hermetic: builds the
agent with in-memory tool adapters seeded per scenario and runs it against the
real model via Runner, asserting on the structured decision. Runs with only a
model credential (no GCP) — the production AgentEvaluator path would require
live BigQuery/Pub-Sub for the tools. Skip-guarded for the unit CI job.
"""
import json
import os

import pytest

pytest.importorskip("google.adk", reason="google-adk not installed (unit job)")

if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI")):
    pytest.skip("no model credential for eval run", allow_module_level=True)

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

from msm_breaker.application.triage_agent import build_triage_agent  # noqa: E402
from msm_breaker.domain import EscalationAction, Signal  # noqa: E402
from msm_breaker.infrastructure.signal_source import InMemorySignalSource  # noqa: E402

pytestmark = pytest.mark.asyncio


async def _run(agent, payload: dict) -> dict:
    sessions = InMemorySessionService()
    runner = Runner(agent=agent, app_name="eval", session_service=sessions)
    await sessions.create_session(app_name="eval", user_id="u", session_id="s")
    msg = types.Content(role="user", parts=[types.Part(text=json.dumps(payload))])
    async for _ in runner.run_async(user_id="u", session_id="s", new_message=msg):
        pass
    state = (await sessions.get_session(app_name="eval", user_id="u", session_id="s")).state
    out = state.get("triage")
    return out.model_dump() if hasattr(out, "model_dump") else out


async def test_severe_sustained_breach_escalates():
    signals = [Signal("psi:affinity_score", 0.42, 0.1, 1), Signal("psi:rpc_14d", 0.31, 0.1, 1)]
    agent = build_triage_agent(InMemorySignalSource(signals))
    out = await _run(agent, {"kind": "null_or_zero_rate", "value": 0.08,
                             "threshold": 0.03, "occurred_at_ms": 1})
    assert out and out["escalate"] is True


async def test_marginal_latency_not_sev1_page():
    agent = build_triage_agent(InMemorySignalSource([]))
    out = await _run(agent, {"kind": "latency", "value": 1.02,
                             "threshold": 1.0, "occurred_at_ms": 1})
    # A marginal blip with no correlated signals should not be a SEV1 page.
    assert out
    assert not (out["action"] == EscalationAction.PAGE_ONCALL.value and out["severity"] == "sev1")
