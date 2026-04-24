from msm_reconciliation.application import LoadReconciliationWindow
from msm_reconciliation.domain import ReconciliationRow, PredictionSource


class _Repo:
    def __init__(self, rows): self.rows = rows
    def fetch_window(self, s, e): return self.rows


def _row(end_ms):
    return ReconciliationRow(
        click_id="c", predicted_rpc=1, realized_rpc=1,
        source=PredictionSource.MODEL, window_ends_at_ms=end_ms,
    )


def test_splits_completed_and_pending():
    uc = LoadReconciliationWindow(_Repo([_row(500), _row(2000)]))
    r = uc.execute(0, 3000, now_ms=1000)
    assert len(r.completed) == 1 and r.completed[0].window_ends_at_ms == 500
    assert len(r.pending) == 1 and r.pending[0].window_ends_at_ms == 2000
