# ADR 0005 — ADK agents only where a reasoning step exists

- Status: Accepted
- Date: 2026-05-29
- Context tag: Agentic ops

## Context

Architectural Rules §1 names Python 3.12+ for "agentic orchestration" but the
platform ships zero agents today — every service is deterministic, DTO-driven
clean architecture. A request was made to move the platform to Google ADK
(Agent Development Kit) agents on Vertex Agent Engine.

A full sweep (six services) found exactly three workflows that contain a genuine
*reasoning* step — a judgment a human currently supplies that no code expresses:

1. **ml-pipeline / drift** — `detect_drift.py` mechanically picks the worst
   verdict. It cannot answer "is this PSI breach actionable — retrain, alert, or
   ignore?" or "which features are driving it?".
2. **bounds-calibration** — `propose_bounds()` computes new bounds; the judgment
   of "is this shift real vs transient vs upstream data-quality noise, and what
   justification does the reviewer need?" is supplied by a human today.
3. **breaker-automation** — `should_trip()` is a provably-correct threshold rule,
   but post-trip *triage* (correlate signals, hypothesise cause, decide
   escalation) is human judgment with no code.

The other three services have **no reasoning step**:
`scoring-api` (Rust hot path, §1 p99<50ms), `reconciliation` (BigQuery join),
`activation` (Pub/Sub→SSGTM/OCI bridge). They are pure I/O.

## Decision

1. **Convert to ADK `LlmAgent` only the three reasoning workflows above.** Each is
   one bounded context → one agent (preserves §3.5 "one MCP server per context",
   restated as "one agent per context").

2. **`scoring-api`, `reconciliation`, `activation` are NOT converted.** Putting an
   LLM on the per-click scoring path would violate §1 (p99<50ms) by 1–2 orders
   of magnitude and add nondeterminism to a revenue path. The others gain nothing
   from reasoning. Converting them would be §7 anti-pattern territory (ceremony
   without value).

3. **The LLM reasons; the domain decides.** Every existing pure decision
   (`should_trip`, `propose_bounds`, `DriftScore.verdict`) stays a deterministic
   domain function exposed to the agent as a read-only tool. The LLM never
   replaces the decision math — it interprets the outputs and chooses which
   side-effecting tool to call. §5 "domain ≥95%, zero mocks" is therefore
   preserved unchanged.

4. **Every state-mutating action is schema-gated (§4).** An agent's structured
   output is validated against an explicit Pydantic schema and re-validated into a
   domain value object (invariants in the constructor) *before* any write. The
   LLM cannot retrain, open a PR, or page on-call on free text.

5. **The breaker trip path stays deterministic and synchronous.** `should_trip()`
   → kill-switch `engage()` runs exactly as today, NOT behind the LLM. The triage
   agent runs after/in parallel and has **no** kill-switch tool — it can neither
   trip nor un-trip the breaker.

## Layer mapping (§2)

```
domain/         unchanged — pure decisions + immutable value objects
application/    the LlmAgent definition + tool wiring lives here; imports domain
                only; may import google.adk
infrastructure/ existing ports become the agent's read tools; new write adapters
                (notifier, PR gateway) implement domain ports
presentation/   new Vertex Agent Engine entrypoint per agent
```

import-linter `domain-purity` already forbids `google` (hence `google.adk`),
`pydantic`, and `functions_framework` in domain — no change to the contract.

## Consequences

**Positive**
- Reasoning that was tribal/manual becomes encoded, observable, and testable.
- Blast radius is contained to three event-driven, low-volume services; the
  revenue hot path is untouched.

**Negative**
- Three services now depend on an LLM → new failure modes (latency, cost,
  nondeterminism), new testing regime (ADR 0006) and new observability (ADR 0007).

**Neutral**
- DTOs do not go away — they become the agents' typed I/O contracts.

## Conflict handling (§0)

No PRD/principle conflict. §1's "agentic orchestration" clause is now exercised;
§1's hot-path Rust mandate is explicitly honoured by *not* converting scoring.
