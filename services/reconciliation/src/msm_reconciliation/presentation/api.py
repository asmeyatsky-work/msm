"""FastAPI app serving /reconciliation to the dashboard. §4 schema validation at the edge."""
from __future__ import annotations
import os
import time
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from msm_reconciliation.application import LoadReconciliationWindow
from msm_reconciliation.infrastructure.bigquery_repo import BigQueryReconciliationRepo

app = FastAPI(title="msm-reconciliation")

_project = os.environ["GCP_PROJECT"]
_dataset = os.environ["BQ_DATASET"]
_use_case = LoadReconciliationWindow(BigQueryReconciliationRepo(_project, _dataset))


class RowOut(BaseModel):
    click_id: str = Field(min_length=1)
    predicted_rpc: float = Field(ge=0)
    realized_rpc: float = Field(ge=0)
    source: str
    window_ends_at_ms: int = Field(ge=0)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/reconciliation", response_model=list[RowOut])
def reconciliation(
    start: int = Query(ge=0),
    end: int = Query(ge=0),
    include_pending: bool = Query(False),
) -> list[RowOut]:
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")
    now_ms = int(time.time() * 1000)
    result = _use_case.execute(start, end, now_ms)
    rows = list(result.completed) + (list(result.pending) if include_pending else [])
    return [
        RowOut(
            click_id=r.click_id,
            predicted_rpc=r.predicted_rpc,
            realized_rpc=r.realized_rpc,
            source=r.source.value,
            window_ends_at_ms=r.window_ends_at_ms,
        ) for r in rows
    ]
