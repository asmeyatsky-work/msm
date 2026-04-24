import pytest
from msm_reconciliation.domain import ReconciliationRow, PredictionSource


def _row(**overrides):
    base = dict(click_id="c", predicted_rpc=1.0, realized_rpc=1.5,
                source=PredictionSource.MODEL, window_ends_at_ms=1000)
    base.update(overrides)
    return ReconciliationRow(**base)


def test_residual():
    assert _row().residual == 0.5


def test_completeness():
    r = _row(window_ends_at_ms=1000)
    assert r.is_complete(1000)
    assert not r.is_complete(999)


@pytest.mark.parametrize("field,value", [
    ("click_id", ""), ("predicted_rpc", -1), ("realized_rpc", -1), ("window_ends_at_ms", -1),
])
def test_rejects_invalid(field, value):
    with pytest.raises(ValueError):
        _row(**{field: value})
