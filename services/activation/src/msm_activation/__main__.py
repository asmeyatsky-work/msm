"""Activation Cloud Run entry point.

Receives Pub/Sub push messages containing a `PredictionEnvelope` JSON body
and forwards them to SA360 via the configured channel (ADR 0001).

Runs on the PORT injected by Cloud Run (defaults to 8080).
"""
from __future__ import annotations
import base64
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException

from msm_activation.application import PublishPrediction
from msm_activation.domain import ActivationMode, PredictionEnvelope


def _build_use_case() -> PublishPrediction | None:
    mode_str = os.environ.get("ACTIVATION_MODE", "ssgtm_phoebe")
    mode = ActivationMode(mode_str)

    ssgtm_url = os.environ.get("SSGTM_ENDPOINT")
    oci_url = os.environ.get("OCI_ENDPOINT")

    # Only instantiate channels if their endpoints are configured; this lets
    # first deploy pass without SSGTM/OCI wired yet.
    from msm_activation.infrastructure.ssgtm_channel import SsgtmChannel
    from msm_activation.infrastructure.oci_channel import OciChannel

    class _Noop:
        def push(self, _envelope): pass

    ssgtm = SsgtmChannel(ssgtm_url, api_key_ref="") if ssgtm_url else _Noop()
    oci   = OciChannel(oci_url) if oci_url else _Noop()
    return PublishPrediction(mode, oci, ssgtm)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.use_case = _build_use_case()
    yield


app = FastAPI(title="msm-activation", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/")
async def pubsub_push(request: Request) -> dict:
    """Pub/Sub push subscription handler."""
    body = await request.json()
    msg = body.get("message", {})
    raw = base64.b64decode(msg.get("data", "")).decode("utf-8") if msg.get("data") else "{}"
    payload = json.loads(raw)
    try:
        envelope = PredictionEnvelope(
            click_id=payload["click_id"],
            correlation_id=payload.get("correlation_id", ""),
            predicted_rpc=float(payload["predicted_rpc"]),
            source=payload.get("source", "MODEL"),
            model_version=payload.get("model_version", "unknown"),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"invalid envelope: {e}") from e

    request.app.state.use_case.execute(envelope)
    return {"status": "accepted"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
