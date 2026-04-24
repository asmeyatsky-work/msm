"""In-memory ReconciliationRepo. Used by E2E smoke tests and local development."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Sequence

from msm_reconciliation.domain import PredictionSource, ReconciliationRow
from msm_reconciliation.application.ports import ReconciliationRepo


class MemoryReconciliationRepo(ReconciliationRepo):
    def __init__(self, rows: Sequence[ReconciliationRow]) -> None:
        self._rows = list(rows)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "MemoryReconciliationRepo":
        raw = json.loads(Path(path).read_text())
        rows = [
            ReconciliationRow(
                click_id=r["click_id"],
                predicted_rpc=float(r["predicted_rpc"]),
                realized_rpc=float(r["realized_rpc"]),
                source=PredictionSource(r["source"]),
                window_ends_at_ms=int(r["window_ends_at_ms"]),
            )
            for r in raw
        ]
        return cls(rows)

    def fetch_window(self, start_ms: int, end_ms: int) -> Sequence[ReconciliationRow]:
        return [r for r in self._rows if start_ms <= r.window_ends_at_ms <= end_ms]
