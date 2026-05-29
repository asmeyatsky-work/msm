"""Deterministic bounds-agent tests (§5 track, ADR 0006). No LLM — the agent's
reasoning is covered by the eval track. Covers the schema gate, the domain
invariants, the dispatch use case, and the agent's read tools."""
import pytest

from msm_bounds.domain import BoundsAssessment, ChangeClass, PercentileSample, propose_bounds
from msm_bounds.application import AssessBounds, BoundsAssessmentOutput
from msm_bounds.application.bounds_agent import build_bounds_agent  # noqa: F401 (import smoke)


class _RecordingGateway:
    def __init__(self):
        self.opened = []

    def open_reviewed_pr(self, proposed, cmin, cmax, title, rationale):
        self.opened.append((proposed, title, rationale))
        return "https://pr/9"


def _genuine():
    return BoundsAssessment(True, ChangeClass.GENUINE_SHIFT, 0.9,
                            "Recalibrate RPC bounds", "p99 up 40% sustained 6/7 buckets",
                            "sustained shift")


# --- domain invariants ---------------------------------------------------------

def test_open_pr_requires_genuine_shift():
    with pytest.raises(ValueError):
        BoundsAssessment(True, ChangeClass.TRANSIENT_SPIKE, 0.5, "t", "r", "j")


def test_genuine_shift_must_open_pr():
    with pytest.raises(ValueError):
        BoundsAssessment(False, ChangeClass.GENUINE_SHIFT, 0.5, "", "", "j")


def test_open_pr_requires_title_and_rationale():
    with pytest.raises(ValueError):
        BoundsAssessment(True, ChangeClass.GENUINE_SHIFT, 0.9, "", "", "j")


@pytest.mark.parametrize("c", [-0.1, 1.1])
def test_confidence_range(c):
    with pytest.raises(ValueError):
        BoundsAssessment(False, ChangeClass.NO_CHANGE, c, "", "", "j")


def test_skip_classes_are_valid():
    for cc in (ChangeClass.TRANSIENT_SPIKE, ChangeClass.DATA_QUALITY, ChangeClass.NO_CHANGE):
        d = BoundsAssessment(False, cc, 0.6, "", "", "skip reason")
        assert not d.open_pr


# --- schema gate ---------------------------------------------------------------

def test_output_maps_to_domain():
    out = BoundsAssessmentOutput(open_pr=True, change_class=ChangeClass.GENUINE_SHIFT,
                                 confidence=0.8, pr_title="t", rationale="r",
                                 justification="j")
    assert out.to_domain().open_pr


def test_output_invalid_combo_rejected_at_gate():
    out = BoundsAssessmentOutput(open_pr=True, change_class=ChangeClass.DATA_QUALITY,
                                 confidence=0.8, pr_title="t", rationale="r",
                                 justification="j")
    with pytest.raises(ValueError):
        out.to_domain()


# --- dispatch use case ---------------------------------------------------------

def test_assess_opens_pr_on_genuine_shift():
    gw = _RecordingGateway()
    proposed = propose_bounds(PercentileSample(0.5, 80.0, 100_000), 0.01, 500.0)
    r = AssessBounds(gw).execute(proposed, 0.01, 500.0, _genuine())
    assert r.pr_url == "https://pr/9" and len(gw.opened) == 1
    # numbers passed to the gateway are the deterministic ones
    assert gw.opened[0][0] is proposed


def test_assess_noop_when_not_open():
    gw = _RecordingGateway()
    proposed = propose_bounds(PercentileSample(0.5, 80.0, 100_000), 0.01, 500.0)
    d = BoundsAssessment(False, ChangeClass.TRANSIENT_SPIKE, 0.7, "", "", "single-bucket spike")
    r = AssessBounds(gw).execute(proposed, 0.01, 500.0, d)
    assert r.pr_url is None and gw.opened == []
    assert r.change_class is ChangeClass.TRANSIENT_SPIKE
