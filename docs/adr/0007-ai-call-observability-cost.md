# ADR 0007 — Per-AI-call observability and cost accounting

- Status: Accepted
- Date: 2026-05-29
- Context tag: Agentic ops
- Relates to: ADR 0005

## Context

Architectural Rules §6 already mandates, for every AI call: "log model ID,
version, prompt hash, tokens in/out, latency, cost." Until ADR 0005 no service
made an AI call, so this clause was dormant. The three ADK agents now make LLM
calls and the clause becomes live and mandatory.

Separately, project memory flags that Vertex endpoint spend is already accruing
and that no spend-increasing scale-up is in scope (single Searce env). LLM token
cost must therefore be measured and bounded, not assumed negligible.

## Decision

1. **Per-AI-call log line.** Each `LlmAgent` registers an ADK
   `after_model_callback` that emits one structured JSON log per model call with:
   `model_id`, `model_version`, `prompt_hash` (sha256 of rendered prompt, no
   raw prompt — §6 "zero PII"), `tokens_in`, `tokens_out`, `latency_ms`,
   `cost_usd` (tokens × published unit price for the model), `correlation_id`,
   and `agent_name`. Logs propagate the existing OTel trace context (§6).

2. **RED metrics per agent and per tool** (§6): rate, errors, duration for each
   agent invocation and each `FunctionTool` call.

3. **Cost is bounded by event volume, not click volume.** The three converted
   workflows are event-driven and low-frequency:
   - drift triage: per drift-evaluation run (daily/scheduled),
   - bounds calibration: per calibration run (scheduled),
   - breaker triage: per anomaly incident (rare by design).
   None is on the per-click path. Expected LLM spend is bounded to these events;
   a `cost_usd` daily-sum metric with an alert threshold makes any regression
   visible. This keeps the work inside the "no spend-increasing scale-up"
   constraint — it adds bounded, observable, event-scoped spend, not per-request
   spend.

## Consequences

- **Positive:** AI cost is a first-class, alertable metric from day one; §6 is
  satisfied uniformly with the existing OTel/structlog stack.
- **Negative:** a small fixed engineering cost to wire the callback into each
  agent and to maintain the model→unit-price table.
- **Neutral:** model unit prices change; the price table is config, not code, and
  is reviewed when models are upgraded.

## Note on code sharing

The `after_model_callback` is duplicated as a small (~40-line, stdlib+structlog)
`infrastructure/ai_call_log.py` in each of the three agent services rather than
extracted to a shared `msm-agent-obs` package. This is deliberate: every service
builds its image from its own local Docker context (`COPY src; pip install .`)
and the repo has no shared-Python-lib precedent, so a cross-service path
dependency would break the independent build/deploy model (and a registry-
published lib is out of scope per the single-env constraint). If a fourth agent
service appears, revisit with a published package + an ADR.

## Conflict handling (§0)

No conflict. This operationalises a §6 clause that was previously dormant.
