"""ML Ops MCP server. Wraps msm_ml.application use cases (§3.5)."""
from __future__ import annotations
import os
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

from msm_ml.application import TrainModel, DetectDrift
from msm_ml.infrastructure.bigquery_feature_repo import BigQueryFeatureRepo
from msm_ml.infrastructure.xgboost_trainer import XGBoostTrainer
from msm_ml.infrastructure.vertex_registry import VertexModelRegistry

PROJECT = os.environ["GCP_PROJECT"]
DATASET = os.environ["BQ_DATASET"]
REGION = os.environ.get("GCP_REGION", "us-central1")

mcp = FastMCP("msm-mlops")


class TrainInput(BaseModel):
    model_id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)


@mcp.tool()
def train_model(payload: TrainInput) -> dict:
    """Kick off a training run. Write tool (§3.5)."""
    uc = TrainModel(
        features=BigQueryFeatureRepo(PROJECT, DATASET),
        trainer=XGBoostTrainer(),
        registry=VertexModelRegistry(PROJECT, REGION),
    )
    r = uc.execute(payload.model_id, payload.start_ms, payload.end_ms)
    return {"model_version": r.model_version.qualified(), "n_rows": r.n_rows}


if __name__ == "__main__":
    mcp.run()
