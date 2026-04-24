"""SA360 Offline Conversion Import channel (Option A / Hybrid interim)."""
from __future__ import annotations
import httpx
from msm_activation.domain import PredictionEnvelope
from msm_activation.application import ActivationChannel


class OciChannel(ActivationChannel):
    def __init__(self, endpoint: str, timeout_s: float = 1.0) -> None:
        self._endpoint = endpoint
        self._timeout_s = timeout_s

    def push(self, envelope: PredictionEnvelope) -> None:
        with httpx.Client(timeout=self._timeout_s) as client:
            client.post(self._endpoint, json={
                "gclid_equivalent": envelope.click_id,  # GCLID stripping risk — PRD §2.1
                "conversion_value": envelope.predicted_rpc,
            })
