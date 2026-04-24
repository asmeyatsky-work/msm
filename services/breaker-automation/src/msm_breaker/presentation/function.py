"""Cloud Function entry point. Pub/Sub-triggered by rpc-anomaly topic.
§4: validates the incoming payload; rejects by default."""
from __future__ import annotations
import base64
import json
import os

import functions_framework
from pydantic import BaseModel, Field

from msm_breaker.application import HandleAnomaly
from msm_breaker.domain import AnomalyEvent, AnomalyKind
from msm_breaker.infrastructure.secret_manager_writer import SecretManagerKillSwitchWriter


class _Payload(BaseModel):
    kind: AnomalyKind
    value: float = Field(ge=0)
    threshold: float = Field(ge=0)
    occurred_at_ms: int = Field(ge=0)


_use_case = HandleAnomaly(
    SecretManagerKillSwitchWriter(os.environ["GCP_PROJECT"], os.environ["RUNTIME_CONFIG_SECRET"]),
)


@functions_framework.cloud_event
def on_anomaly(cloud_event) -> None:  # type: ignore[no-untyped-def]
    raw = cloud_event.data.get("message", {}).get("data", "")
    decoded = base64.b64decode(raw).decode("utf-8") if raw else "{}"
    payload = _Payload.model_validate_json(decoded)
    event = AnomalyEvent(
        kind=payload.kind, value=payload.value,
        threshold=payload.threshold, occurred_at_ms=payload.occurred_at_ms,
    )
    _use_case.execute(event)
