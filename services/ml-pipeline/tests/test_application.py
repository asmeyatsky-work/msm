"""Application tests — §5: ≥85% coverage, mock ports only."""
from typing import Sequence
from msm_ml.application import TrainModel, DetectDrift
from msm_ml.domain import FeatureVector, ModelVersion, DriftScore, DriftVerdict


class _Repo:
    def __init__(self, rows): self.rows = rows
    def load_training_frame(self, s, e): return self.rows


class _Trainer:
    def train(self, rows): return b"art"


class _Registry:
    def __init__(self): self.last = None
    def register(self, artifact, model_id):
        self.last = ModelVersion(model_id, "v1", 0); return self.last
    def latest(self, model_id): return self.last


class _Monitor:
    def __init__(self, scores): self.scores = scores
    def score(self, b, c): return self.scores


def _fv():
    return FeatureVector("c", "m", "US", 1, 0.5, 1, 1, 1, False, 0.5, 1)


def test_train_model_end_to_end():
    uc = TrainModel(_Repo([(_fv(), 5.0)]), _Trainer(), _Registry())
    r = uc.execute("rpc", 0, 1)
    assert r.n_rows == 1
    assert r.model_version.model_id == "rpc"


def test_train_model_rejects_empty_window():
    uc = TrainModel(_Repo([]), _Trainer(), _Registry())
    try:
        uc.execute("rpc", 0, 1)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_detect_drift_elevates_worst_verdict():
    uc = DetectDrift(_Monitor([DriftScore("a", 0.05), DriftScore("b", 0.30)]))
    verdict, _ = uc.execute(0, 1)
    assert verdict == DriftVerdict.BREACH
