"""SSGTM channel — ADR 0001 recommended path."""
from __future__ import annotations
import httpx
from msm_activation.domain import PredictionEnvelope
from msm_activation.application import ActivationChannel


class SsgtmChannel(ActivationChannel):
    def __init__(self, endpoint: str, api_key_ref: str, timeout_s: float = 0.5) -> None:
        self._endpoint = endpoint
        self._api_key_ref = api_key_ref  # Secret Manager resource name (§4)
        self._timeout_s = timeout_s      # §3.2: explicit timeout

    def push(self, envelope: PredictionEnvelope) -> None:
        with httpx.Client(timeout=self._timeout_s) as client:
            client.post(self._endpoint, json={
                "click_id": envelope.click_id,
                "value": envelope.predicted_rpc,
                "correlation_id": envelope.correlation_id,
                "source": envelope.source,
                "model_version": envelope.model_version,
            })
