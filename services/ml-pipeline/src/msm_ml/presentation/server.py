"""HTTP entrypoint for the drift triage agent. Layer: presentation.
Stack: FastAPI on Cloud Run (ADR 0005 deploy). Triggered by Cloud Scheduler
(daily, after psi_daily materializes). Computes the drift windows from "now" and
the model id from env (MODEL_ID). Health at /health.

RETRAIN is dispatched to the existing ml-pipeline-train Cloud Run Job rather
than trained in-process (see infrastructure.cloud_run_trainer) — wired in
agent_app from env.
"""
from __future__ import annotations
import os
import time

import structlog
from fastapi import FastAPI

from msm_ml.presentation.agent_app import run_triage

_log = structlog.get_logger()
app = FastAPI(title="drift-triage-agent")

_DAY_MS = 86_400_000


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def run() -> dict[str, str | None]:
    now_ms = int(time.time() * 1000)
    model_id = os.environ.get("MODEL_ID", "rpc")
    baseline_window_ms = now_ms - 7 * _DAY_MS
    dispatch = await run_triage(model_id, baseline_window_ms, now_ms, now_ms)
    model_version = dispatch.model_version.qualified() if dispatch.model_version else None
    _log.info("drift_triage_run", action=dispatch.action.value,
              model_version=model_version, detail=dispatch.detail)
    return {"action": dispatch.action.value, "model_version": model_version,
            "detail": dispatch.detail}
