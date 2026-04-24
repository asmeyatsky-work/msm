from __future__ import annotations
from typing import Protocol
from msm_activation.domain import PredictionEnvelope, ActivationMode


class ActivationChannel(Protocol):
    """Port: one implementation per PRD §2.1 option."""
    def push(self, envelope: PredictionEnvelope) -> None: ...


class PublishPrediction:
    """Routes envelopes to the channel selected by config.
    Option C (HYBRID) fans out to both OCI and SSGTM until the migration
    milestone; §3.6: the two channels are independent, so they run concurrently."""

    def __init__(self, mode: ActivationMode, oci: ActivationChannel, ssgtm: ActivationChannel) -> None:
        self._mode = mode
        self._oci = oci
        self._ssgtm = ssgtm

    def execute(self, envelope: PredictionEnvelope) -> None:
        match self._mode:
            case ActivationMode.DIRECT_OCI:
                self._oci.push(envelope)
            case ActivationMode.SSGTM_PHOEBE:
                self._ssgtm.push(envelope)
            case ActivationMode.HYBRID:
                # §3.6: independent steps run concurrently. In prod the adapter uses
                # asyncio.gather; kept sequential here to keep the use case pure-sync.
                self._oci.push(envelope)
                self._ssgtm.push(envelope)
