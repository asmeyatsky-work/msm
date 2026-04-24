from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
from msm_reconciliation.domain import ReconciliationRow
from .ports import ReconciliationRepo


@dataclass(frozen=True, slots=True)
class LoadResult:
    completed: Sequence[ReconciliationRow]
    pending: Sequence[ReconciliationRow]


class LoadReconciliationWindow:
    """Fetch rows and split by conversion-window completeness.
    Pending rows are useful for operators to see volume but not for quality metrics."""

    def __init__(self, repo: ReconciliationRepo) -> None:
        self._repo = repo

    def execute(self, start_ms: int, end_ms: int, now_ms: int) -> LoadResult:
        rows = self._repo.fetch_window(start_ms, end_ms)
        completed, pending = [], []
        for r in rows:
            (completed if r.is_complete(now_ms) else pending).append(r)
        return LoadResult(completed=completed, pending=pending)
