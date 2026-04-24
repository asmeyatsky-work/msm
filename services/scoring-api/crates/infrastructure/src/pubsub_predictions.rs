//! Pub/Sub-backed PredictionSink. Publishes a JSON envelope per prediction
//! to `rpc-predictions`; a BigQuery subscription lands it in `rpc_predictions`
//! for the reconciliation view (PRD §4.2).

use crate::gcp_auth::MetadataTokenSource;
use async_trait::async_trait;
use base64::Engine;
use msm_scoring_domain::ports::{PortError, PredictionRecord, PredictionSink};
use std::sync::Arc;
use std::time::Duration;

pub struct PubSubPredictions {
    http: reqwest::Client,
    tokens: Arc<MetadataTokenSource>,
    url: String,
}

impl PubSubPredictions {
    pub fn new(project: String, topic: String, per_call_timeout: Duration) -> Self {
        let api_root = std::env::var("PUBSUB_API_ROOT")
            .unwrap_or_else(|_| "https://pubsub.googleapis.com".into());
        Self::with_api_root(api_root, project, topic, per_call_timeout)
    }

    pub fn with_api_root(
        api_root: String,
        project: String,
        topic: String,
        per_call_timeout: Duration,
    ) -> Self {
        let http = reqwest::Client::builder()
            .timeout(per_call_timeout)
            .build()
            .expect("client");
        Self {
            http,
            tokens: Arc::new(MetadataTokenSource::new(per_call_timeout)),
            url: format!("{api_root}/v1/projects/{project}/topics/{topic}:publish"),
        }
    }
}

#[async_trait]
impl PredictionSink for PubSubPredictions {
    async fn record(&self, r: PredictionRecord) -> Result<(), PortError> {
        let token = self.tokens.token().await.map_err(PortError::Upstream)?;
        let data = serde_json::json!({
            "click_id": r.click_id,
            "correlation_id": r.correlation_id,
            "predicted_rpc": r.predicted_rpc,
            "source": r.source,
            "model_version": r.model_version,
            "ts_ms": r.ts_ms,
        })
        .to_string();
        let body = serde_json::json!({
            "messages": [{
                "data": base64::engine::general_purpose::STANDARD.encode(data.as_bytes()),
                "attributes": {"click_id": r.click_id, "source": r.source},
            }]
        });
        let resp = self
            .http
            .post(&self.url)
            .bearer_auth(token)
            .json(&body)
            .send()
            .await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        if !resp.status().is_success() {
            return Err(PortError::Upstream(format!(
                "pubsub status={}",
                resp.status()
            )));
        }
        Ok(())
    }
}
