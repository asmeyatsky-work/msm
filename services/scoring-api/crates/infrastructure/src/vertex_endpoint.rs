use std::sync::Arc;
use std::time::Duration;
use async_trait::async_trait;
use msm_scoring_domain::{
    ClickFeatures, Rpc,
    ports::{ModelEndpoint, PortError},
};
use crate::gcp_auth::MetadataTokenSource;

/// Vertex AI online prediction endpoint.
/// Auth via Workload Identity metadata-server token (§4).
/// §3.2: explicit per-call timeout.
pub struct VertexEndpoint {
    http: reqwest::Client,
    endpoint_url: String,
    model_version: String,
    tokens: Arc<MetadataTokenSource>,
}

impl VertexEndpoint {
    pub fn new(endpoint_url: String, model_version: String, per_call_timeout: Duration) -> Self {
        let http = reqwest::Client::builder().timeout(per_call_timeout).build().expect("client");
        let tokens = Arc::new(MetadataTokenSource::new(per_call_timeout));
        Self { http, endpoint_url, model_version, tokens }
    }
}

#[async_trait]
impl ModelEndpoint for VertexEndpoint {
    async fn predict(&self, features: &ClickFeatures) -> Result<(Rpc, String), PortError> {
        let token = self.tokens.token().await.map_err(PortError::Upstream)?;
        let body = serde_json::json!({
            "instances": [{
                "click_id": features.click_id().as_str(),
                "cerberus_score": features.cerberus_score(),
                "rpc_7d": features.rpc_7d(),
                "rpc_14d": features.rpc_14d(),
                "rpc_30d": features.rpc_30d(),
            }]
        });
        let resp = self.http.post(&self.endpoint_url)
            .bearer_auth(token)
            .json(&body).send().await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        if !resp.status().is_success() {
            return Err(PortError::Upstream(format!("status={}", resp.status())));
        }
        let parsed: serde_json::Value = resp.json().await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        // Vertex AI returns {"predictions": [x]} for a regression endpoint.
        let raw = parsed.pointer("/predictions/0")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| PortError::Upstream("missing predictions[0]".into()))?;
        let rpc = Rpc::try_new(raw).map_err(|e| PortError::Upstream(e.to_string()))?;
        Ok((rpc, self.model_version.clone()))
    }
}
