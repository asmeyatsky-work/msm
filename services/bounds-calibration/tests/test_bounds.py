import pytest
from msm_bounds.domain import PercentileSample, propose_bounds
from msm_bounds.application import Calibrate


def test_accepts_meaningful_change():
    sample = PercentileSample(p1=0.1, p99=50.0, n=100_000)
    r = propose_bounds(sample, current_min=0.01, current_max=500.0)
    assert r is not None
    assert r.min_rpc == 0.1
    assert r.max_rpc == 75.0  # 50 * 1.5


def test_rejects_small_sample():
    sample = PercentileSample(p1=0.1, p99=50.0, n=50)
    assert propose_bounds(sample, 0.01, 500.0) is None


def test_rejects_no_material_change():
    sample = PercentileSample(p1=0.01, p99=333.0, n=100_000)
    # new max = 333 * 1.5 = 499.5 — within 10% of 500
    # new min = max(0.01, 0.01) = 0.01 — identical
    assert propose_bounds(sample, 0.01, 500.0) is None


def test_rejects_invalid_sample():
    with pytest.raises(ValueError):
        PercentileSample(p1=5.0, p99=1.0, n=100)


class _SrcFixed:
    def __init__(self, sample): self.sample_ = sample
    def sample(self, h): return self.sample_


class _GwRecording:
    def __init__(self): self.opened = []
    def open_bounds_pr(self, proposed, cmin, cmax):
        self.opened.append(proposed); return "https://pr/1"


def test_calibrate_opens_pr_when_change_warranted():
    src = _SrcFixed(PercentileSample(p1=0.5, p99=80.0, n=100_000))
    gw = _GwRecording()
    r = Calibrate(src, gw).execute(lookback_hours=168, current_min=0.01, current_max=500.0)
    assert r.pr_url == "https://pr/1"
    assert len(gw.opened) == 1


def test_calibrate_noop_when_not_warranted():
    src = _SrcFixed(PercentileSample(p1=0.5, p99=80.0, n=100))
    gw = _GwRecording()
    r = Calibrate(src, gw).execute(lookback_hours=168, current_min=0.01, current_max=500.0)
    assert r.pr_url is None
    assert gw.opened == []
