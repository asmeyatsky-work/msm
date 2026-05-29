"""Drift triage agent (ADK). Layer: application.
Ports used as read-only tools: DriftMonitor (via DetectDrift), ModelRegistry.
MCP: none. The agent has NO retrain/alert tool — it emits a triage; the
deterministic TriageDrift use case performs the side effect.
Stack: Python 3.12 + google-adk on Vertex Agent Engine (ADR 0001 §1, ADR 0005).

SequentialAgent: investigator (read tools) -> decider (output_schema). ADK
imports deferred so the package imports without google-adk present.
"""
from __future__ import annotations
import os
from typing import Any

from .detect_drift import DetectDrift
from .ports import ModelRegistry
from .schemas import DriftTriageOutput

_DEFAULT_MODEL = os.environ.get("DRIFT_MODEL", "gemini-2.5-flash")

_INVESTIGATOR_INSTRUCTION = """\
You investigate feature drift for an ad-revenue prediction model. GATHER
EVIDENCE only — do not decide yet.

Steps:
1. Call `drift_scores` to get per-feature PSI and each feature's verdict
   (healthy <0.1, warn <0.25, breach >=0.25). You never recompute or override
   these numbers.
2. Call `latest_model` to see how recently the live model was trained.
3. Write a concise analysis: which features are in WARN/BREACH and by how much,
   whether the move looks like a real distribution shift vs a likely seasonal /
   one-off pattern, and whether the model is stale enough that a retrain would
   actually help. Name the driver features explicitly.
"""

_DECIDER_INSTRUCTION = """\
You decide the drift action using ONLY the investigator's analysis. Output JSON
matching the schema. Rules:
- action="retrain" REQUIRES at least one driver feature and a
  retrain_lookback_days in [1, 365]; reserve it for a genuine, sustained BREACH
  where a fresher model would plausibly help.
- action="alert" REQUIRES at least one driver and retrain_lookback_days=0; use
  when humans should look but an automatic retrain is not clearly warranted.
- action="noop" with retrain_lookback_days=0 when drift is benign/seasonal.
- Be conservative about retraining — it is high blast radius. justification is
  always required and must cite the concrete PSI values.
"""


def build_drift_agent(detect: DetectDrift, registry: ModelRegistry,
                      model: str = _DEFAULT_MODEL, after_model_callback=None):
    """Construct the SequentialAgent. `after_model_callback` injected from
    presentation (§2) for §6 AI-call logging (ADR 0007)."""
    from google.adk.agents import LlmAgent, SequentialAgent  # deferred import

    def drift_scores(baseline_window_ms: int, current_window_ms: int) -> dict[str, Any]:
        """Read-only tool: per-feature PSI + worst verdict."""
        worst, scores = detect.execute(baseline_window_ms, current_window_ms)
        return {
            "worst_verdict": worst.value,
            "scores": [{"feature": s.feature_name, "psi": s.psi,
                        "verdict": s.verdict().value} for s in scores],
        }

    def latest_model(model_id: str) -> dict[str, Any]:
        """Read-only tool: the currently-registered model version, if any."""
        mv = registry.latest(model_id)
        if mv is None:
            return {"model": None}
        return {"model": {"qualified": mv.qualified(),
                          "trained_at_epoch_ms": mv.trained_at_epoch_ms}}

    investigator = LlmAgent(
        name="drift_investigator",
        model=model,
        instruction=_INVESTIGATOR_INSTRUCTION,
        tools=[drift_scores, latest_model],
        output_key="analysis",
        after_model_callback=after_model_callback,
    )
    decider = LlmAgent(
        name="drift_decider",
        model=model,
        instruction=_DECIDER_INSTRUCTION,
        output_schema=DriftTriageOutput,
        output_key="triage",
        after_model_callback=after_model_callback,
    )
    return SequentialAgent(name="drift_triage", sub_agents=[investigator, decider])
