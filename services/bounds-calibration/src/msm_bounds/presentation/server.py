"""HTTP entrypoint for the bounds calibration agent. Layer: presentation.
Stack: FastAPI on Cloud Run (ADR 0005 deploy). Triggered by Cloud Scheduler
(weekly). Reads the same env knobs as the deterministic cli.py Job
(LOOKBACK_HOURS / CURRENT_MIN / CURRENT_MAX), so the scheduler can POST an empty
body. Health at /health.
"""
from __future__ import annotations
import os

import structlog
from fastapi import FastAPI

from msm_bounds.presentation.agent_app import run_calibration

_log = structlog.get_logger()
app = FastAPI(title="bounds-calibration-agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def run() -> dict[str, str | None]:
    lookback = int(os.environ.get("LOOKBACK_HOURS", "168"))  # 7d default
    current_min = float(os.environ["CURRENT_MIN"])
    current_max = float(os.environ["CURRENT_MAX"])
    result = await run_calibration(lookback, current_min, current_max)
    _log.info("bounds_calibration_run", pr_url=result.pr_url,
              change_class=result.change_class.value, reason=result.reason)
    return {"pr_url": result.pr_url, "reason": result.reason,
            "change_class": result.change_class.value}
