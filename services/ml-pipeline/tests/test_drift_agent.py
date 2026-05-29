"""Deterministic drift-agent tests (§5 track, ADR 0006). No LLM — reasoning is
covered by the eval track. Covers the schema gate, domain invariants, the
dispatch use case (incl. the high-blast-radius RETRAIN path), and the read tools."""
import pytest

from msm_ml.domain import (
    DriftAction, DriftScore, DriftTriage, DriftVerdict, ModelVersion,
)
from msm_ml.application import DriftTriageOutput, TriageDrift
from msm_ml.application.drift_agent import build_drift_agent  # noqa: F401 (import smoke)
from msm_ml.infrastructure.alert_sink import InMemoryAlertSink
from msm_ml.infrastructure.drift_monitor import InMemoryDriftMonitor


# --- domain invariants ---------------------------------------------------------

def test_retrain_requires_drivers():
    with pytest.raises(ValueError):
        DriftTriage(DriftAction.RETRAIN, DriftVerdict.BREACH, (), 30, "j")


def test_retrain_requires_lookback_in_range():
    with pytest.raises(ValueError):
        DriftTriage(DriftAction.RETRAIN, DriftVerdict.BREACH, ("affinity_score",), 0, "j")
    with pytest.raises(ValueError):
        DriftTriage(DriftAction.RETRAIN, DriftVerdict.BREACH, ("affinity_score",), 999, "j")


def test_alert_forbids_lookback():
    with pytest.raises(ValueError):
        DriftTriage(DriftAction.ALERT, DriftVerdict.WARN, ("affinity_score",), 14, "j")


def test_noop_forbids_lookback():
    with pytest.raises(ValueError):
        DriftTriage(DriftAction.NOOP, DriftVerdict.WARN, (), 14, "j")


def test_valid_triages():
    DriftTriage(DriftAction.RETRAIN, DriftVerdict.BREACH, ("affinity_score",), 30, "sustained breach")
    DriftTriage(DriftAction.ALERT, DriftVerdict.WARN, ("device",), 0, "watch")
    DriftTriage(DriftAction.NOOP, DriftVerdict.WARN, (), 0, "seasonal")


# --- schema gate ---------------------------------------------------------------

def test_output_maps_to_domain():
    out = DriftTriageOutput(action=DriftAction.RETRAIN, severity=DriftVerdict.BREACH,
                            drivers=["affinity_score"], retrain_lookback_days=30,
                            justification="psi 0.4 on affinity")
    d = out.to_domain()
    assert d.action is DriftAction.RETRAIN and d.drivers == ("affinity_score",)


def test_output_invalid_combo_rejected_at_gate():
    out = DriftTriageOutput(action=DriftAction.RETRAIN, severity=DriftVerdict.BREACH,
                            drivers=[], retrain_lookback_days=30, justification="x")
    with pytest.raises(ValueError):
        out.to_domain()


# --- dispatch use case ---------------------------------------------------------

class _FakeTrainModel:
    """Stands in for TrainModel — records the window it was asked to retrain on."""
    def __init__(self):
        self.calls = []

    def execute(self, model_id, start_ms, end_ms):
        self.calls.append((model_id, start_ms, end_ms))
        from msm_ml.application import TrainModelResult
        return TrainModelResult(ModelVersion(model_id, "v2", end_ms), n_rows=123)


def test_retrain_dispatches_train_with_derived_window():
    train = _FakeTrainModel()
    alert = InMemoryAlertSink()
    now = 1_000 * 86_400_000  # day 1000 in ms
    d = DriftTriage(DriftAction.RETRAIN, DriftVerdict.BREACH, ("affinity_score",), 30, "breach")
    out = TriageDrift(train, alert).execute("rpc", d, now)
    assert out.action is DriftAction.RETRAIN and out.model_version.version == "v2"
    (model_id, start_ms, end_ms) = train.calls[0]
    assert end_ms == now and start_ms == now - 30 * 86_400_000
    assert alert.emitted == []


def test_alert_dispatches_alert_not_train():
    train = _FakeTrainModel()
    alert = InMemoryAlertSink()
    d = DriftTriage(DriftAction.ALERT, DriftVerdict.WARN, ("device",), 0, "watch")
    out = TriageDrift(train, alert).execute("rpc", d, 1)
    assert out.action is DriftAction.ALERT and out.model_version is None
    assert len(alert.emitted) == 1 and train.calls == []


def test_noop_dispatches_nothing():
    train = _FakeTrainModel()
    alert = InMemoryAlertSink()
    d = DriftTriage(DriftAction.NOOP, DriftVerdict.WARN, (), 0, "seasonal")
    out = TriageDrift(train, alert).execute("rpc", d, 1)
    assert out.action is DriftAction.NOOP and train.calls == [] and alert.emitted == []


# --- read tools (in-memory monitor) --------------------------------------------

def test_in_memory_drift_monitor_feeds_detect():
    from msm_ml.application import DetectDrift
    monitor = InMemoryDriftMonitor([DriftScore("affinity_score", 0.4), DriftScore("device", 0.05)])
    worst, scores = DetectDrift(monitor).execute(0, 1)
    assert worst is DriftVerdict.BREACH and len(scores) == 2
