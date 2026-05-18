"""Application tests — §5: ≥85% coverage, mock ports only."""
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
        self.last = ModelVersion(model_id, "v1", 0)
        return self.last
    def latest(self, model_id): return self.last


class _Monitor:
    def __init__(self, scores): self.scores = scores
    def score(self, b, c): return self.scores


def _fv():
    return FeatureVector(
        click_id="c", vertical_id="credit_cards",
        device="m", geo="GB", hour_of_day=1,
        product_type="cashback", card_product_id="card-x",
        query_intent="compare", affinity_score=0.5,
        prior_applicant=False, income_band_bucket=None,
        auction_pressure=0.5, rpc_14d=1.0, rpc_60d=1.0,
        visits_prev_30d=1,
        phoebe_calculator_used=False, phoebe_guides_read=0,
        phoebe_cards_compared=0, phoebe_session_engagement_s=0.0,
    )


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
