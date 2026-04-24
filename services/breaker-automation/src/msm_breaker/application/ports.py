from __future__ import annotations
from typing import Protocol


class KillSwitchWriter(Protocol):
    def engage(self, reason: str) -> None:
        """Flip the kill switch. Idempotent — writing an identical value is a no-op."""
