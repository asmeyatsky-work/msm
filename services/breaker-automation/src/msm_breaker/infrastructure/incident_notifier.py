"""IncidentNotifier adapter. Layer: infrastructure. Implements
application.IncidentNotifier. §4: every write emits an audit event
(actor, action, before/after hash). Workload Identity only.

Publishes escalations to the incident Pub/Sub topic (consumed by the on-call
paging integration). Scaffolded: the publish call is a TODO against the real
topic. `page` and `annotate` differ only by the `paging` flag on the payload so
the downstream router decides whether to wake someone.
"""
from __future__ import annotations
import json

import structlog

from msm_breaker.application.ports import IncidentNotifier
from msm_breaker.domain import AnomalyEvent, TriageDecision

_log = structlog.get_logger()


class PubSubIncidentNotifier(IncidentNotifier):
    def __init__(self, project: str, topic: str) -> None:
        self._project = project
        self._topic = topic

    def page(self, decision: TriageDecision, event: AnomalyEvent) -> str:
        return self._emit(decision, event, paging=True)

    def annotate(self, decision: TriageDecision, event: AnomalyEvent) -> str:
        return self._emit(decision, event, paging=False)

    def _emit(self, decision: TriageDecision, event: AnomalyEvent, *, paging: bool) -> str:
        payload = {
            "paging": paging,
            "severity": decision.severity.value,
            "action": decision.action.value,
            "cause_hypothesis": decision.cause_hypothesis,
            "justification": decision.justification,
            "anomaly_kind": event.kind.value,
            "anomaly_value": event.value,
            "anomaly_threshold": event.threshold,
            "occurred_at_ms": event.occurred_at_ms,
        }
        # TODO(agentic-ops): publish to projects/{project}/topics/{topic} with a
        # request timeout (§4) and emit the §4 audit event (actor=breaker-triage,
        # action=escalate, after_hash=sha256(payload)).
        incident_ref = f"pubsub://{self._topic}#{event.occurred_at_ms}"
        _log.info("incident_escalation_stub", paging=paging,
                  severity=decision.severity.value, ref=incident_ref,
                  payload_bytes=len(json.dumps(payload)))
        return incident_ref
