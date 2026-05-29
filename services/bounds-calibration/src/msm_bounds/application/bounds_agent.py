"""Bounds calibration agent (ADK). Layer: application.
Ports used as read-only tools: PercentileSource, DistributionHistory, plus the
pure domain `propose_bounds`. MCP: none. Has NO PR-write tool — it emits an
assessment; the deterministic `AssessBounds` use case performs the PR write.
Stack: Python 3.12 + google-adk on Vertex Agent Engine (ADR 0001 §1, ADR 0005).

Same shape as the breaker triage agent: a SequentialAgent of
  1. investigator — read tools (current sample, candidate bounds, history),
  2. decider     — no tools, output_schema=BoundsAssessmentOutput.
ADK imports are deferred so the package imports without google-adk present.
"""
from __future__ import annotations
import os
from typing import Any

from msm_bounds.domain import propose_bounds
from .ports import DistributionHistory, PercentileSource
from .schemas import BoundsAssessmentOutput

_DEFAULT_MODEL = os.environ.get("BOUNDS_MODEL", "gemini-2.5-flash")

_INVESTIGATOR_INSTRUCTION = """\
You investigate a proposed RPC prediction-bounds change for an ad-revenue model.
GATHER EVIDENCE only — do not decide yet.

Steps:
1. Call `candidate_bounds` to get the deterministic proposed [min, max] (or null
   if the policy already says no change). You never invent or alter these numbers.
2. Call `current_sample` for the current-window p1/p99/n.
3. Call `distribution_history` to see recent buckets.
4. Write a concise analysis: is the p99/p1 move SUSTAINED across buckets (genuine
   shift) or confined to one bucket (transient spike)? Is `n` adequate and are
   percentiles plausible (else data-quality)? State which it looks like and why.
"""

_DECIDER_INSTRUCTION = """\
You decide whether to open a bounds-recalibration PR, using ONLY the
investigator's analysis. Output JSON matching the schema. Rules:
- open_pr=true REQUIRES change_class="genuine_shift" plus a pr_title and a
  reviewer-facing rationale citing the concrete percentiles/buckets.
- A transient spike, a data-quality artefact, or no material change MUST set
  open_pr=false with the matching change_class (never "genuine_shift").
- Be conservative: when evidence is weak, prefer not to churn the bounds.
- justification is always required.
"""


def build_bounds_agent(
    source: PercentileSource, history: DistributionHistory,
    model: str = _DEFAULT_MODEL, after_model_callback=None,
):
    """Construct the SequentialAgent. `after_model_callback` is injected from
    presentation (§2 layering) for §6 AI-call logging (ADR 0007)."""
    from google.adk.agents import LlmAgent, SequentialAgent  # deferred import

    def current_sample(lookback_hours: int) -> dict[str, Any]:
        """Read-only tool: current-window percentile sample."""
        s = source.sample(lookback_hours)
        return {"p1": s.p1, "p99": s.p99, "n": s.n}

    def candidate_bounds(lookback_hours: int, current_min: float, current_max: float) -> dict[str, Any]:
        """Read-only tool: the deterministic proposed bounds (or null)."""
        s = source.sample(lookback_hours)
        proposed = propose_bounds(s, current_min, current_max)
        if proposed is None:
            return {"proposed": None, "reason": "policy: no material change"}
        return {"proposed": {"min_rpc": proposed.min_rpc, "max_rpc": proposed.max_rpc,
                             "reason": proposed.reason}}

    def distribution_history(lookback_hours: int, buckets: int = 7) -> list[dict[str, Any]]:
        """Read-only tool: recent bucketed percentile samples."""
        return [{"p1": s.p1, "p99": s.p99, "n": s.n}
                for s in history.recent_samples(lookback_hours, buckets)]

    investigator = LlmAgent(
        name="bounds_investigator",
        model=model,
        instruction=_INVESTIGATOR_INSTRUCTION,
        tools=[candidate_bounds, current_sample, distribution_history],
        output_key="analysis",
        after_model_callback=after_model_callback,
    )
    decider = LlmAgent(
        name="bounds_decider",
        model=model,
        instruction=_DECIDER_INSTRUCTION,
        output_schema=BoundsAssessmentOutput,
        output_key="assessment",
        after_model_callback=after_model_callback,
    )
    return SequentialAgent(name="bounds_calibration", sub_agents=[investigator, decider])
