"""IncidentNotifier adapter. Layer: infrastructure. Implements
application.IncidentNotifier. §4: Workload Identity; every write emits an audit
event (actor, action, after-hash); no PII.

Publishes escalations to the incident Pub/Sub topic (consumed by the on-call
paging integration). `page` and `annotate` differ only by the `paging`
attribute, so the downstream router decides whether to wake someone.
"""
from __future__ import annotations
import hashlib
import json

import structlog
from google.cloud import pubsub_v1

from msm_breaker.application.ports import IncidentNotifier
from msm_breaker.domain import AnomalyEvent, TriageDecision

_log = structlog.get_logger()


class PubSubIncidentNotifier(IncidentNotifier):
    def __init__(self, project: str, topic: str, *, publish_timeout_s: float = 10.0) -> None:
        self._publisher = pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(project, topic)
        self._publish_timeout_s = publish_timeout_s

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
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        after_hash = hashlib.sha256(data).hexdigest()
        future = self._publisher.publish(
            self._topic_path, data,
            paging=str(paging).lower(), severity=decision.severity.value,
        )
        message_id = future.result(timeout=self._publish_timeout_s)  # §3.2 bounded
        # §4 audit event: actor / action / after-hash, append-only via Cloud Logging.
        _log.info("audit", actor="breaker-triage", action="escalate",
                  paging=paging, after_hash=after_hash, message_id=message_id,
                  correlation=f"anomaly:{event.occurred_at_ms}")
        return f"pubsub://{self._topic_path}#{message_id}"
