from __future__ import annotations
from typing import Protocol, Sequence
from msm_reconciliation.domain import ReconciliationRow


class ReconciliationRepo(Protocol):
    def fetch_window(self, start_ms: int, end_ms: int) -> Sequence[ReconciliationRow]: ...
