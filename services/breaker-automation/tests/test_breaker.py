import pytest
from msm_breaker.domain import AnomalyEvent, AnomalyKind, should_trip
from msm_breaker.application import HandleAnomaly


class _Writer:
    def __init__(self): self.engaged = []
    def engage(self, reason): self.engaged.append(reason)


def test_trip_on_null_rate():
    e = AnomalyEvent(AnomalyKind.NULL_OR_ZERO_RATE, 0.04, 0.03, 1)
    d = should_trip(e)
    assert d.trip


def test_no_trip_below_threshold():
    e = AnomalyEvent(AnomalyKind.NULL_OR_ZERO_RATE, 0.01, 0.03, 1)
    assert not should_trip(e).trip


def test_handle_anomaly_engages_writer():
    w = _Writer()
    uc = HandleAnomaly(w)
    tripped = uc.execute(AnomalyEvent(AnomalyKind.FEATURE_DRIFT, 0.3, 0.25, 1))
    assert tripped
    assert len(w.engaged) == 1


def test_handle_anomaly_noop_when_not_breached():
    w = _Writer()
    uc = HandleAnomaly(w)
    assert not uc.execute(AnomalyEvent(AnomalyKind.LATENCY, 0.5, 1.0, 1))
    assert w.engaged == []


@pytest.mark.parametrize("field,value", [
    ("value", -1), ("threshold", -1), ("occurred_at_ms", -1),
])
def test_event_rejects_invalid(field, value):
    base = dict(kind=AnomalyKind.LATENCY, value=0.1, threshold=0.2, occurred_at_ms=1)
    base[field] = value
    with pytest.raises(ValueError):
        AnomalyEvent(**base)
