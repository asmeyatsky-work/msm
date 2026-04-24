"""Domain tests — §5: ≥95% coverage, zero mocks."""
import pytest
from msm_ml.domain import FeatureVector, DriftScore, DriftVerdict, ModelVersion


def _fv(**overrides):
    base = dict(
        click_id="c", device="mobile", geo="US", hour_of_day=10,
        cerberus_score=0.8, rpc_7d=1.0, rpc_14d=1.0, rpc_30d=1.0,
        is_payday_week=False, auction_pressure=0.5, visits_prev_30d=2,
    )
    base.update(overrides)
    return FeatureVector(**base)


def test_feature_vector_happy():
    fv = _fv()
    assert fv.as_map()["rpc_7d"] == 1.0


@pytest.mark.parametrize("field,value", [
    ("hour_of_day", 24),
    ("cerberus_score", 1.5),
    ("rpc_7d", -0.1),
    ("click_id", ""),
])
def test_feature_vector_rejects(field, value):
    with pytest.raises(ValueError):
        _fv(**{field: value})


def test_drift_verdicts():
    assert DriftScore("x", 0.05).verdict() == DriftVerdict.HEALTHY
    assert DriftScore("x", 0.15).verdict() == DriftVerdict.WARN
    assert DriftScore("x", 0.30).verdict() == DriftVerdict.BREACH


def test_drift_rejects_negative():
    with pytest.raises(ValueError):
        DriftScore("x", -0.1)


def test_model_version_qualified():
    mv = ModelVersion("rpc", "v1", 0)
    assert mv.qualified() == "rpc@v1"


def test_model_version_rejects_empty():
    with pytest.raises(ValueError):
        ModelVersion("", "v1", 0)
