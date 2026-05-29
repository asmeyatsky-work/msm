"""Bounds calibration agent entrypoint. Layer: presentation.
Stack: Python 3.12 + google-adk on Vertex Agent Engine (ADR 0005).

Orchestration (ADR 0005 — LLM reasons, domain decides):
  1. deterministic: sample percentiles + `propose_bounds` -> canonical numbers.
  2. if no candidate, return early WITHOUT an LLM call (cost, ADR 0007).
  3. else run the agent to classify the change + author the PR rationale.
  4. validate its output (§4 gate) and let `AssessBounds` open the PR with the
     deterministic numbers (never numbers the LLM produced).

Does not replace the non-agent `cli.py` Calibrate path; runs alongside it.
This is the one layer allowed to import both application and infrastructure (§2).
"""
from __future__ import annotations
import json
import os

from msm_bounds.application import AssessBounds, AssessResult, BoundsAssessmentOutput
from msm_bounds.application.bounds_agent import build_bounds_agent
from msm_bounds.domain import ChangeClass, propose_bounds
from msm_bounds.infrastructure.ai_call_log import after_model_callback
from msm_bounds.infrastructure.bigquery_source import BigQueryPercentileSource
from msm_bounds.infrastructure.distribution_history import BigQueryDistributionHistory
from msm_bounds.infrastructure.reviewed_github_gateway import ReviewedGitHubPullRequestGateway

_PROJECT = os.environ.get("GCP_PROJECT", "")
_DATASET = os.environ.get("BQ_DATASET", "")

# Module-level agent for Vertex Agent Engine discovery. Built only when the data
# env is present (i.e. at deploy/runtime); None on bare import so unit tests and
# `adk` tooling can import the package without GCP credentials.
if _PROJECT and _DATASET:
    _source = BigQueryPercentileSource(_PROJECT, _DATASET)
    _history = BigQueryDistributionHistory(_PROJECT, _DATASET)
    root_agent = build_bounds_agent(_source, _history, after_model_callback=after_model_callback)
else:
    _source = _history = root_agent = None


def _build_gateway() -> ReviewedGitHubPullRequestGateway:
    return ReviewedGitHubPullRequestGateway(
        token=os.environ["GITHUB_TOKEN"],          # §4: from Secret Manager
        repo_full_name=os.environ["GITHUB_REPO"],
        config_path=os.environ.get("CONFIG_PATH", "infra/runtime_config.json"),
    )


async def run_calibration(lookback_hours: int, current_min: float, current_max: float) -> AssessResult:
    if _source is None or root_agent is None:
        raise RuntimeError("GCP_PROJECT/BQ_DATASET not configured")

    # 1. Deterministic candidate.
    sample = _source.sample(lookback_hours)
    proposed = propose_bounds(sample, current_min, current_max)
    if proposed is None:
        # 2. No candidate — skip the LLM entirely.
        return AssessResult(None, "no change warranted", ChangeClass.NO_CHANGE)

    # 3. Agent classifies the change + authors the rationale.
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    sid = f"bounds-{lookback_hours}-{current_min}-{current_max}"
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="bounds-calibration",
                    session_service=session_service)
    await session_service.create_session(
        app_name="bounds-calibration", user_id="bounds", session_id=sid)
    prompt = types.Content(role="user", parts=[types.Part(text=json.dumps({
        "lookback_hours": lookback_hours,
        "current_min": current_min, "current_max": current_max,
    }))])
    async for _ in runner.run_async(user_id="bounds", session_id=sid, new_message=prompt):
        pass

    session = await session_service.get_session(
        app_name="bounds-calibration", user_id="bounds", session_id=sid)
    raw = session.state.get("assessment")
    output = BoundsAssessmentOutput.model_validate(
        raw if isinstance(raw, dict) else json.loads(raw))
    assessment = output.to_domain()  # §4 gate — raises before any PR write

    # 4. Deterministic dispatch with the deterministic numbers.
    gateway = _build_gateway() if assessment.open_pr else None
    use_case = AssessBounds(gateway) if gateway else AssessBounds(_NullGateway())
    return use_case.execute(proposed, current_min, current_max, assessment)


class _NullGateway:
    """Used only when the agent declined to open a PR — never called."""
    def open_reviewed_pr(self, *a, **k) -> str:  # pragma: no cover
        raise AssertionError("gateway invoked despite open_pr=False")
