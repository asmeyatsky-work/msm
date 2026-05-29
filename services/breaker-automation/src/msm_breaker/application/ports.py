"""Ports (§3.2): every external dependency is an interface implemented in
infrastructure. Layer: application."""
from __future__ import annotations
from typing import Protocol, Sequence

from msm_breaker.domain import AnomalyEvent, Signal, TriageDecision


class KillSwitchWriter(Protocol):
    def engage(self, reason: str) -> None:
        """Flip the kill switch. Idempotent — writing an identical value is a no-op."""


class SignalSource(Protocol):
    """Read-only evidence for triage. The agent correlates these with the
    triggering anomaly. No write capability — triage cannot mutate state here."""
    def recent(self, window_ms: int) -> Sequence[Signal]: ...


class IncidentNotifier(Protocol):
    """Escalation writes. Only ever called by the deterministic use case AFTER a
    `TriageDecision` has been validated (§4) — never directly by the LLM."""
    def page(self, decision: TriageDecision, event: AnomalyEvent) -> str:
        """Page on-call. Returns an incident id/url."""

    def annotate(self, decision: TriageDecision, event: AnomalyEvent) -> str:
        """Record on the incident timeline without paging. Returns an id/url."""
