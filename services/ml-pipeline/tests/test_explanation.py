import pytest
from msm_ml.domain import Attribution
from msm_ml.application import ExplainModel


def test_top_features_sorts_by_absolute_value():
    a = Attribution(base_value=1.0, contributions={"a": -2.0, "b": 0.5, "c": 1.0})
    assert a.top_features(2) == [("a", -2.0), ("c", 1.0)]


def test_attribution_rejects_empty_name():
    with pytest.raises(ValueError):
        Attribution(base_value=0, contributions={"": 0.1})


class _Stub:
    def __init__(self, batch): self.batch = batch
    def explain(self, features): return self.batch


def test_explain_model_empty_batch_returns_empty():
    uc = ExplainModel(_Stub([]))
    assert uc.execute([]) == []
