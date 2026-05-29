"""Per-AI-call observability (§6, ADR 0007). Layer: infrastructure.

ADK `after_model_callback` emitting one structured log line per model call:
model id, prompt hash (sha256, no raw prompt — §6 zero PII), tokens in/out,
estimated cost. Duck-typed against ADK args so this imports without google-adk.
(Per-service copy; a shared `msm-agent-obs` lib is the natural future refactor.)
"""
from __future__ import annotations
import hashlib
from typing import Any

import structlog

_log = structlog.get_logger()

# USD per 1M tokens (input, output). Config, reviewed on model upgrade (ADR 0007).
_PRICE_PER_MTOK: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
}


def _cost_usd(model: str, tin: int, tout: int) -> float | None:
    price = _PRICE_PER_MTOK.get(model)
    if price is None:
        return None
    pin, pout = price
    return round((tin / 1_000_000) * pin + (tout / 1_000_000) * pout, 6)


def after_model_callback(callback_context: Any, llm_response: Any) -> None:
    model = getattr(callback_context, "model", None) or "unknown"
    usage = getattr(llm_response, "usage_metadata", None)
    tin = getattr(usage, "prompt_token_count", 0) or 0
    tout = getattr(usage, "candidates_token_count", 0) or 0
    raw = str(getattr(llm_response, "content", "") or "")
    prompt_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    _log.info(
        "ai_call",
        model_id=model,
        prompt_hash=prompt_hash,
        tokens_in=tin,
        tokens_out=tout,
        cost_usd=_cost_usd(model, tin, tout),
        agent_name=getattr(callback_context, "agent_name", None),
    )
    return None
