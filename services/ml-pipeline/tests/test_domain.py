"""Domain tests — §5: ≥95% coverage, zero mocks."""
import pytest
from msm_ml.domain import FeatureVector, DriftScore, DriftVerdict, ModelVersion


def _fv(**overrides):
    base = dict(
        click_id="c", vertical_id="credit_cards",
        device="mobile", geo="GB", hour_of_day=10,
        product_type="cashback", card_product_id="card-x",
        query_intent="compare", affinity_score=0.7,
        prior_applicant=False, income_band_bucket="mid",
        auction_pressure=0.5, rpc_14d=1.0, rpc_60d=1.0,
        visits_prev_30d=2,
    )
    base.update(overrides)
    return FeatureVector(**base)


def test_feature_vector_happy():
    fv = _fv()
    assert fv.as_map()["rpc_14d"] == 1.0
    assert fv.as_map()["product_type"] == "cashback"


@pytest.mark.parametrize("field,value", [
    ("hour_of_day", 24),
    ("affinity_score", 1.5),
    ("rpc_14d", -0.1),
    ("click_id", ""),
    ("vertical_id", ""),
    ("product_type", ""),
    ("income_band_bucket", "vip"),
])
def test_feature_vector_rejects(field, value):
    with pytest.raises(ValueError):
        _fv(**{field: value})


def test_feature_vector_accepts_null_income_band():
    fv = _fv(income_band_bucket=None)
    assert fv.as_map()["income_band_bucket"] is None


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
