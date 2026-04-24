"""Pure decision: given an anomaly, do we trip? Separated from the I/O side
so the policy is unit-testable and reviewable."""
from __future__ import annotations
from dataclasses import dataclass
from .event import AnomalyEvent, AnomalyKind


@dataclass(frozen=True, slots=True)
class BreakerDecision:
    trip: bool
    reason: str


def should_trip(event: AnomalyEvent) -> BreakerDecision:
    if not event.breached():
        return BreakerDecision(trip=False, reason="within threshold")
    # All three kinds are first-class PRD §5 conditions; treat equally.
    match event.kind:
        case AnomalyKind.NULL_OR_ZERO_RATE:
            return BreakerDecision(trip=True, reason="null/zero rate above threshold")
        case AnomalyKind.FEATURE_DRIFT:
            return BreakerDecision(trip=True, reason="feature drift PSI breach")
        case AnomalyKind.LATENCY:
            return BreakerDecision(trip=True, reason="latency SLO breach")
