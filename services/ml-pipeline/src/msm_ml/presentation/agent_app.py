"""Drift triage agent entrypoint. Layer: presentation.
Stack: Python 3.12 + google-adk on Vertex Agent Engine (ADR 0005).

Orchestration (ADR 0005 — LLM reasons, domain decides):
  1. deterministic: DetectDrift over the windows.
  2. if worst verdict is HEALTHY, return NOOP WITHOUT an LLM call (cost, ADR 0007).
  3. else run the agent to triage (retrain / alert / noop) + name drivers.
  4. validate its output (§4 gate) and let TriageDrift dispatch — RETRAIN is
     executed by the deterministic TrainModel, not the LLM.

Does not replace the non-agent `cli.py` train path. This layer may import both
application and infrastructure (§2); it injects the §6 AI-call callback here.
"""
from __future__ import annotations
import json
import os

from msm_ml.application import (
    DetectDrift, DriftTriageOutput, TrainModel, TriageDispatch, TriageDrift,
)
from msm_ml.application.drift_agent import build_drift_agent
from msm_ml.domain import DriftAction, DriftVerdict
from msm_ml.infrastructure.ai_call_log import after_model_callback
from msm_ml.infrastructure.alert_sink import LogAlertSink
from msm_ml.infrastructure.bigquery_feature_repo import BigQueryFeatureRepo
from msm_ml.infrastructure.drift_monitor import BigQueryDriftMonitor
from msm_ml.infrastructure.vertex_registry import VertexModelRegistry
from msm_ml.infrastructure.xgboost_trainer import XGBoostTrainer

_PROJECT = os.environ.get("GCP_PROJECT", "")
_DATASET = os.environ.get("BQ_DATASET", "")
_REGION = os.environ.get("VERTEX_REGION", "us-central1")
_BUCKET = os.environ.get("STAGING_BUCKET", "")

if _PROJECT and _DATASET and _BUCKET:
    _registry = VertexModelRegistry(_PROJECT, _REGION, _BUCKET)
    _detect = DetectDrift(BigQueryDriftMonitor(_PROJECT, _DATASET))
    root_agent = build_drift_agent(_detect, _registry, after_model_callback=after_model_callback)
else:
    _registry = _detect = root_agent = None


async def run_triage(model_id: str, baseline_window_ms: int, current_window_ms: int,
                     now_ms: int) -> TriageDispatch:
    if _detect is None or root_agent is None:
        raise RuntimeError("GCP_PROJECT/BQ_DATASET/STAGING_BUCKET not configured")

    # 1-2. Deterministic detection; skip the LLM when healthy.
    worst, _scores = _detect.execute(baseline_window_ms, current_window_ms)
    if worst is DriftVerdict.HEALTHY:
        return TriageDispatch(DriftAction.NOOP, None, "no drift observed")

    # 3. Agent triages.
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    sid = f"drift-{model_id}-{current_window_ms}"
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="drift-triage", session_service=session_service)
    await session_service.create_session(app_name="drift-triage", user_id="ml", session_id=sid)
    prompt = types.Content(role="user", parts=[types.Part(text=json.dumps({
        "model_id": model_id,
        "baseline_window_ms": baseline_window_ms,
        "current_window_ms": current_window_ms,
    }))])
    async for _ in runner.run_async(user_id="ml", session_id=sid, new_message=prompt):
        pass

    session = await session_service.get_session(
        app_name="drift-triage", user_id="ml", session_id=sid)
    raw = session.state.get("triage")
    output = DriftTriageOutput.model_validate(raw if isinstance(raw, dict) else json.loads(raw))
    triage = output.to_domain()  # §4 gate — raises before retrain/alert

    # 4. Deterministic dispatch.
    train = TrainModel(
        features=BigQueryFeatureRepo(_PROJECT, _DATASET),
        trainer=XGBoostTrainer(),
        registry=_registry,
    )
    return TriageDrift(train, LogAlertSink()).execute(model_id, triage, now_ms)
