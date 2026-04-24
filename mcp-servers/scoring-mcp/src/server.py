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

from scopes import require_scope

# §4: no default for externally-facing URLs — reads deferred to first call so
# schemas can be imported for testing without environment.
def _scoring_url() -> str:
    return os.environ["SCORING_API_URL"]

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
@require_scope("scoring.score.write")
async def score_click(payload: ScoreInput) -> dict:
    """Score a click via the Scoring use case. Write tool (§3.5).
    Requires scope `scoring.score.write`; token TTL capped at 15 min (§4)."""
    async with httpx.AsyncClient(timeout=CALL_TIMEOUT_S) as client:
        resp = await client.post(f"{_scoring_url()}/v1/score", json=payload.model_dump())
        resp.raise_for_status()
        return resp.json()


@mcp.resource("scoring://health")
@require_scope("scoring.health.read", ttl_max_s=900)
async def health() -> str:
    """Health probe — read resource (§3.5). Requires `scoring.health.read`."""
    async with httpx.AsyncClient(timeout=CALL_TIMEOUT_S) as client:
        r = await client.get(f"{_scoring_url()}/healthz")
        return r.text


if __name__ == "__main__":
    # §4: install a real verifier at startup. Secret pulled via Workload Identity.
    import base64 as _b64
    from hmac_verifier import HmacVerifier
    from scopes import install_verifier
    secret_b64 = os.environ["MCP_TOKEN_SECRET_B64"]
    install_verifier(HmacVerifier(_b64.b64decode(secret_b64)))
    mcp.run()
