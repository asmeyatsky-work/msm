"""Eval track (ADR 0006). Exercises the agent's reasoning/trajectory with ADK's
AgentEvaluator against the committed eval set. Requires google-adk and a model
credential, so it is skip-guarded — it runs in the dedicated agent-eval CI job,
not the coverage-gating unit job.
"""
import os
import pathlib

import pytest

pytest.importorskip("google.adk", reason="google-adk not installed (unit job)")

if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI")):
    pytest.skip("no model credential for eval run", allow_module_level=True)

_EVALSET = pathlib.Path(__file__).parent.parent / "eval" / "triage.evalset.json"


@pytest.mark.asyncio
async def test_triage_agent_eval():
    from google.adk.evaluation.agent_evaluator import AgentEvaluator

    # Points at the presentation module exposing `root_agent`.
    await AgentEvaluator.evaluate(
        agent_module="msm_breaker.presentation.agent_app",
        eval_dataset_file_path_or_dir=str(_EVALSET),
    )
