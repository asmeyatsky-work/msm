"""FastAPI app serving /reconciliation and /coverage to the dashboard.
§4 schema validation at the edge. Schema: PRD V2 (Credit Cards) §4.2-§4.3.
"""
from __future__ import annotations
import os
import time
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from msm_reconciliation.application import LoadReconciliationWindow

app = FastAPI(title="msm-reconciliation")


def _build_repo():
    """Pick the backend: memory (E2E / local) or BigQuery (prod)."""
    mock_path = os.environ.get("RECONCILIATION_MOCK_JSON")
    if mock_path:
        from msm_reconciliation.infrastructure.memory_repo import MemoryReconciliationRepo
        return MemoryReconciliationRepo.from_json_file(mock_path)
    from msm_reconciliation.infrastructure.bigquery_repo import BigQueryReconciliationRepo
    return BigQueryReconciliationRepo(os.environ["GCP_PROJECT"], os.environ["BQ_DATASET"])


_use_case = LoadReconciliationWindow(_build_repo())


class RowOut(BaseModel):
    click_id: str = Field(min_length=1)
    predicted_rpc: float = Field(ge=0)
    realized_rpc: float = Field(ge=0)
    source: str
    window_ends_at_ms: int = Field(ge=0)
    vertical_id: str = "credit_cards"
    product_type: str = ""
    model_version: str = ""


class CoverageSlice(BaseModel):
    slice_dim: str
    slice_value: str
    clicks: int = Field(ge=0)
    covered_clicks: int = Field(ge=0)
    coverage_rate: float


# /healthz is intercepted by Cloud Run's GFE (returns 404 before reaching the
# container); /health is the path that actually hits FastAPI. Keep /healthz
# aliased so anything still probing the old path keeps working.
@app.get("/health")
@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/reconciliation", response_model=list[RowOut])
def reconciliation(
    start: int = Query(ge=0),
    end: int = Query(ge=0),
    include_pending: bool = Query(False),
    product_type: str | None = Query(None, description="PRD V2 §4.2 filter"),
) -> list[RowOut]:
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")
    now_ms = int(time.time() * 1000)
    result = _use_case.execute(start, end, now_ms)
    rows = list(result.completed) + (list(result.pending) if include_pending else [])
    if product_type:
        rows = [r for r in rows if r.product_type == product_type]
    return [
        RowOut(
            click_id=r.click_id,
            predicted_rpc=r.predicted_rpc,
            realized_rpc=r.realized_rpc,
            source=r.source.value,
            window_ends_at_ms=r.window_ends_at_ms,
            vertical_id=r.vertical_id,
            product_type=r.product_type,
            model_version=r.model_version,
        ) for r in rows
    ]


@app.get("/coverage", response_model=list[CoverageSlice])
def coverage() -> list[CoverageSlice]:
    """PRD V2 §4.3 — slice coverage from the coverage_audit Dataform view.

    Falls back to an empty list if the view is missing (e.g. before Dataform
    has run); the dashboard treats an empty payload as 'no coverage data
    yet'.
    """
    project = os.environ.get("GCP_PROJECT")
    dataset = os.environ.get("BQ_DATASET")
    if not project or not dataset:
        return []
    # Lazy import — memory mode doesn't need google-cloud-bigquery at runtime.
    try:
        from google.cloud import bigquery  # noqa: WPS433
    except ImportError:
        return []
    try:
        client = bigquery.Client(project=project)
        rows = client.query(
            f"SELECT slice_dim, slice_value, clicks, covered_clicks, coverage_rate "
            f"FROM `{project}.{dataset}.coverage_audit`",
            timeout=10.0,
        ).result(timeout=10.0)
    except Exception:
        return []
    return [
        CoverageSlice(
            slice_dim=r["slice_dim"],
            slice_value=r["slice_value"],
            clicks=int(r["clicks"]),
            covered_clicks=int(r["covered_clicks"]),
            coverage_rate=float(r["coverage_rate"] or 0.0),
        )
        for r in rows
    ]
