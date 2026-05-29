# ADR 0006 — Eval-based testing for nondeterministic agents

- Status: Accepted
- Date: 2026-05-29
- Context tag: Agentic ops
- Relates to: ADR 0005

## Context

Architectural Rules §5 sets a hard testing floor: domain ≥95% (zero mocks),
application ≥85% (mock ports only), overall ≥80%, CI blocks merges below
threshold. This floor assumes deterministic code: same input → same output.

The three ADK agents introduced in ADR 0005 are nondeterministic by
construction — an `LlmAgent`'s output varies run to run. Trajectory and final
response cannot be asserted with `assertEqual`. A naïve reading of §5 would
either (a) block all agent merges forever, or (b) be met with meaningless
snapshot tests.

## Decision

§5 is reinterpreted for `LlmAgent` code as a **two-track** regime:

1. **Deterministic track (§5 unchanged).** Everything the agent calls is still
   pure and tested to the existing floor:
   - Domain decisions (`should_trip`, `propose_bounds`, `DriftScore.verdict`):
     ≥95%, zero mocks. Unchanged.
   - The schema-gate mappers (Pydantic output schema → domain value object) and
     the application use cases that perform the actual writes (e.g.
     `TriageAnomaly.execute`): ≥85%, mock ports only. These are deterministic
     given an agent output, so they are unit-tested with hand-written outputs
     including adversarial / malformed ones (reject-by-default per §4).

2. **Eval track (new).** The agent's reasoning and tool-use trajectory are
   exercised with ADK `AgentEvaluator` against committed eval sets
   (`services/<svc>/eval/*.evalset.json`):
   - `response_match_score` (semantic, not exact) with a documented threshold.
   - `tool_trajectory_avg_score` to assert the agent calls the right read tools
     and proposes the right escalation class.
   - Eval sets are version-controlled and reviewed like tests.

## Consequences

- **CI:** the deterministic track gates merges exactly as today (coverage check
  unchanged). The eval track runs as a **separate, required CI job** that needs a
  model credential; thresholds are tuned per agent and recorded in the eval file.
  A failing eval blocks merge but is reported distinctly from coverage.
- Eval runs cost tokens — they run on PRs touching agent code, not on every push.
- The "≥85% application, mock ports only" number is **not** computed over the
  `LlmAgent` definition module (it makes a network call); that module is covered
  by the eval track instead. This carve-out is the deviation §5 requires an ADR
  for.

## Conflict handling (§0)

Principle (§5 "rule not in CI = rule not real") is preserved: both tracks are
CI-enforced. Only the *form* of the agent-module assertion changes.
