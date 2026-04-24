use async_trait::async_trait;
use msm_scoring_domain::ports::{AuditSink, AuditEvent, PortError};

/// Append-only audit sink to a Pub/Sub topic with its own IAM (§4).
/// Kept as a thin adapter — no business decisions.
pub struct PubSubAudit { topic: String }

impl PubSubAudit {
    pub fn new(topic: String) -> Self { Self { topic } }
}

#[async_trait]
impl AuditSink for PubSubAudit {
    async fn record(&self, event: AuditEvent) -> Result<(), PortError> {
        tracing::info!(
            topic = %self.topic,
            actor = %event.actor,
            action = %event.action,
            correlation_id = %event.correlation_id,
            click_id = %event.click_id,
            after_hash = %event.after_hash,
            source = event.source,
            "audit.event"
        );
        Ok(())
    }
}
