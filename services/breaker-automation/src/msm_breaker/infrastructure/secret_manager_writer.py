"""Secret Manager-backed KillSwitchWriter. §4: Workload Identity only."""
from __future__ import annotations
import json
from google.cloud import secretmanager

from msm_breaker.application.ports import KillSwitchWriter


class SecretManagerKillSwitchWriter(KillSwitchWriter):
    """Appends a new version to the runtime-config secret. scoring-api reads the
    latest version on its config-refresh interval and flips its kill flag."""

    def __init__(self, project: str, secret_id: str) -> None:
        self._client = secretmanager.SecretManagerServiceClient()
        self._parent = f"projects/{project}/secrets/{secret_id}"

    def engage(self, reason: str) -> None:
        payload = json.dumps({"kill": True, "reason": reason}).encode("utf-8")
        self._client.add_secret_version(
            request={"parent": self._parent, "payload": {"data": payload}},
        )
