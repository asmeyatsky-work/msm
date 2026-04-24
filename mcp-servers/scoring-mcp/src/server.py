"""Scoring MCP server.

Layer: infrastructure (§2 — MCP servers live in infrastructure and wrap
application use cases). §3.5: Tools = writes, Resources = reads.
Stack: Python 3.12 (§1 default for agentic orchestration).

This server wraps the scoring-api HTTP endpoint. It does NOT embed the use
case — it talks to it over HTTP to preserve process isolation. Agents get
scoped, time-boxed tool access (§4).
"""
from __future__ import annotations
import os
import httpx
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

SCORING_URL = os.environ["SCORING_API_URL"]        # §4: no default for externally-facing URLs
CALL_TIMEOUT_S = float(os.environ.get("MCP_CALL_TIMEOUT_S", "0.2"))  # §3.2 timeout

mcp = FastMCP("msm-scoring")


class ScoreInput(BaseModel):
    click_id: str = Field(min_length=1)
    correlation_id: str
    device: str
    geo: str
    hour_of_day: int = Field(ge=0, le=23)
    query_intent: str
    ad_creative_id: str
    cerberus_score: float = Field(ge=0.0, le=1.0)
    rpc_7d: float = Field(ge=0.0)
    rpc_14d: float = Field(ge=0.0)
    rpc_30d: float = Field(ge=0.0)
    is_payday_week: bool
    auction_pressure: float
    landing_path: str
    visits_prev_30d: int = Field(ge=0)


@mcp.tool()
async def score_click(payload: ScoreInput) -> dict:
    """Score a click via the Scoring use case. Write tool (§3.5)."""
    async with httpx.AsyncClient(timeout=CALL_TIMEOUT_S) as client:
        resp = await client.post(f"{SCORING_URL}/v1/score", json=payload.model_dump())
        resp.raise_for_status()
        return resp.json()


@mcp.resource("scoring://health")
async def health() -> str:
    """Health probe — read resource (§3.5)."""
    async with httpx.AsyncClient(timeout=CALL_TIMEOUT_S) as client:
        r = await client.get(f"{SCORING_URL}/healthz")
        return r.text


if __name__ == "__main__":
    mcp.run()
