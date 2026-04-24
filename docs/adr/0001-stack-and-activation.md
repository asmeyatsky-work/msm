# ADR 0001 — Stack per bounded context; SSGTM activation

- Status: Accepted
- Date: 2026-04-24

## Context

Architectural Rules §1 mandates Rust for hot-path APIs with p99 < 50ms, Python 3.12+ for
ML/agentic work, and TypeScript + React for frontends. PRD §2.1 leaves the Activation Layer
open (Options A/B/C).

## Decision

1. **scoring-api: Rust.** PRD §2.2 requires <100ms serving. Rust is the §1 default for that
   SLO; deviation would need its own ADR.
2. **ml-pipeline, activation, MCP servers: Python 3.12.** §1 default for ML and
   agentic orchestration.
3. **dashboard: TypeScript + React.** §1 default for frontends.
4. **Activation: Option B (SSGTM + gPS Phoebe), recommended in PRD §2.1.** Option A
   (Direct OCI) bypasses Google's native modeling and is losing match rate; Option C
   (Hybrid) only makes sense if customer demands interim value — logged as a variant
   config in the activation service, not a separate codepath.

## Consequences

- Cross-service contracts are Protobuf (§1) in `proto/`.
- Rust workspace enforces §2 via crate boundaries; Python via import-linter; TS via
  eslint-plugin-boundaries. All three checks are required in CI.
- Option C remains reachable by toggling `ACTIVATION_MODE=hybrid` in the activation
  service config — no separate branch.

## Conflict handling (§0)

No PRD/principle conflict detected at this layer.
