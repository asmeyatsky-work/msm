"""Eval track (ADR 0006) for the bounds agent. Hermetic: builds the agent with
in-memory tool adapters seeded per scenario and runs it against the real model,
asserting on the structured decision. Runs with only a model credential.
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

from msm_bounds.application.bounds_agent import build_bounds_agent  # noqa: E402
from msm_bounds.domain import PercentileSample  # noqa: E402
from msm_bounds.infrastructure.distribution_history import InMemoryDistributionHistory  # noqa: E402

pytestmark = pytest.mark.asyncio


class _FixedSource:
    """current-window percentile sample; p99 elevated so a candidate exists."""
    def __init__(self, sample: PercentileSample):
        self._s = sample

    def sample(self, lookback_hours: int) -> PercentileSample:
        return self._s


async def _run(agent, payload: dict) -> dict:
    sessions = InMemorySessionService()
    runner = Runner(agent=agent, app_name="eval", session_service=sessions)
    await sessions.create_session(app_name="eval", user_id="u", session_id="s")
    msg = types.Content(role="user", parts=[types.Part(text=json.dumps(payload))])
    async for _ in runner.run_async(user_id="u", session_id="s", new_message=msg):
        pass
    state = (await sessions.get_session(app_name="eval", user_id="u", session_id="s")).state
    out = state.get("assessment")
    return out.model_dump() if hasattr(out, "model_dump") else out


async def test_sustained_shift_opens_pr():
    # p99 ~120 in every recent bucket → genuine sustained shift vs current max 100.
    source = _FixedSource(PercentileSample(p1=0.5, p99=120.0, n=200_000))
    history = InMemoryDistributionHistory(
        [PercentileSample(0.5, 118.0, 30_000) for _ in range(7)])
    agent = build_bounds_agent(source, history)
    out = await _run(agent, {"lookback_hours": 168, "current_min": 0.01, "current_max": 100.0})
    assert out and out["open_pr"] is True


async def test_single_bucket_spike_declines():
    # 7-day aggregate p99 only mildly over the bound (75 -> proposed max ~112, a
    # ~12% change), and history shows ONE spike day (120) among six flat days (60)
    # — a transient spike, internally consistent with the 75 aggregate.
    source = _FixedSource(PercentileSample(p1=0.5, p99=75.0, n=200_000))
    history = InMemoryDistributionHistory(
        [PercentileSample(0.5, 120.0, 30_000)]
        + [PercentileSample(0.5, 60.0, 30_000) for _ in range(6)])
    agent = build_bounds_agent(source, history)
    out = await _run(agent, {"lookback_hours": 168, "current_min": 0.01, "current_max": 100.0})
    assert out and out["open_pr"] is False
