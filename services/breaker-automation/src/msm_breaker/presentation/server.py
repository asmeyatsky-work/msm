"""HTTP entrypoint for the breaker triage agent. Layer: presentation.
Stack: FastAPI on Cloud Run (ADR 0005 deploy). Receives a Pub/Sub *push*
delivery from the rpc-anomaly topic and runs the triage agent — alongside, not
in place of, the deterministic trip Cloud Function.

§4: validates the push payload, rejects by default. Health at /health
(/healthz is intercepted by Google Frontend — see CD pipeline notes).
"""
from __future__ import annotations
import base64

import structlog
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field, ValidationError

from msm_breaker.domain import AnomalyEvent, AnomalyKind
from msm_breaker.presentation.agent_app import run_triage

_log = structlog.get_logger()
app = FastAPI(title="breaker-triage-agent")


class _Payload(BaseModel):
    kind: AnomalyKind
    value: float = Field(ge=0)
    threshold: float = Field(ge=0)
    occurred_at_ms: int = Field(ge=0)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/")
async def on_push(request: Request) -> Response:
    envelope = await request.json()
    raw = (envelope or {}).get("message", {}).get("data", "")
    decoded = base64.b64decode(raw).decode("utf-8") if raw else "{}"
    try:
        payload = _Payload.model_validate_json(decoded)
    except ValidationError as e:
        # Malformed message: ack (204) so Pub/Sub doesn't poison-loop it.
        _log.warning("breaker_triage_bad_payload", error=str(e))
        return Response(status_code=204)

    event = AnomalyEvent(kind=payload.kind, value=payload.value,
                         threshold=payload.threshold, occurred_at_ms=payload.occurred_at_ms)
    try:
        await run_triage(event)
    except Exception as e:  # noqa: BLE001 — nack (500) so Pub/Sub retries transient failures
        _log.error("breaker_triage_failed", error=str(e))
        return Response(status_code=500)
    return Response(status_code=204)
