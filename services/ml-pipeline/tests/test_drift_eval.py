"""Eval track (ADR 0006) for the drift triage agent. Hermetic: builds the agent
with in-memory tool adapters seeded per scenario and runs it against the real
model, asserting on the structured decision. Runs with only a model credential.
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

from msm_ml.application import DetectDrift  # noqa: E402
from msm_ml.application.drift_agent import build_drift_agent  # noqa: E402
from msm_ml.domain import DriftScore, ModelVersion  # noqa: E402
from msm_ml.infrastructure.drift_monitor import InMemoryDriftMonitor  # noqa: E402

pytestmark = pytest.mark.asyncio


class _StaleRegistry:
    """Live model trained long ago, so a retrain is plausibly helpful."""
    def register(self, artifact, model_id):  # pragma: no cover
        raise NotImplementedError

    def latest(self, model_id):
        return ModelVersion(model_id, "v1", 1_600_000_000_000)  # 2020-09


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


async def test_sustained_breach_does_not_noop():
    monitor = InMemoryDriftMonitor([
        DriftScore("affinity_score", 0.42), DriftScore("auction_pressure", 0.31),
        DriftScore("device", 0.05),
    ])
    agent = build_drift_agent(DetectDrift(monitor), _StaleRegistry())
    out = await _run(agent, {"model_id": "rpc", "baseline_window_ms": 1, "current_window_ms": 2})
    # A multi-feature breach must trigger action (retrain or alert), never noop.
    assert out and out["action"] in {"retrain", "alert"} and out["drivers"]


async def test_single_warn_does_not_retrain():
    monitor = InMemoryDriftMonitor([DriftScore("device", 0.16)])  # warn band only
    agent = build_drift_agent(DetectDrift(monitor), _StaleRegistry())
    out = await _run(agent, {"model_id": "rpc", "baseline_window_ms": 1, "current_window_ms": 2})
    # A single warn-band feature should not trigger a high-blast-radius retrain.
    assert out and out["action"] != "retrain"
