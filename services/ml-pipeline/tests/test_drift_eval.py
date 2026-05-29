"""Eval track (ADR 0006) for the drift triage agent. Skip-guarded: needs
google-adk + a model credential, so it runs in the agent-eval CI job."""
import os
import pathlib

import pytest

pytest.importorskip("google.adk", reason="google-adk not installed (unit job)")

if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI")):
    pytest.skip("no model credential for eval run", allow_module_level=True)

_EVALSET = pathlib.Path(__file__).parent.parent / "eval" / "drift.evalset.json"


@pytest.mark.asyncio
async def test_drift_agent_eval():
    from google.adk.evaluation.agent_evaluator import AgentEvaluator

    await AgentEvaluator.evaluate(
        agent_module="msm_ml.presentation.agent_app",
        eval_dataset_file_path_or_dir=str(_EVALSET),
    )
