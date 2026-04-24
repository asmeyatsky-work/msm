use std::sync::Arc;
use std::time::Duration;
use async_trait::async_trait;
use msm_scoring_domain::{
    ClickFeatures, Clv,
    ports::{ClvEndpoint, PortError},
};
use crate::gcp_auth::MetadataTokenSource;

/// Vertex AI CLV prediction endpoint (PRD §6). Separate model from RPC.
pub struct VertexClvEndpoint {
    http: reqwest::Client,
    endpoint_url: String,
    tokens: Arc<MetadataTokenSource>,
}

impl VertexClvEndpoint {
    pub fn new(endpoint_url: String, per_call_timeout: Duration) -> Self {
        let http = reqwest::Client::builder().timeout(per_call_timeout).build().expect("client");
        Self {
            http, endpoint_url,
            tokens: Arc::new(MetadataTokenSource::new(per_call_timeout)),
        }
    }
}

#[async_trait]
impl ClvEndpoint for VertexClvEndpoint {
    async fn predict(&self, features: &ClickFeatures) -> Result<Clv, PortError> {
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
        let resp = self.http.post(&self.endpoint_url).bearer_auth(token)
            .json(&body).send().await.map_err(|e| PortError::Upstream(e.to_string()))?;
        if !resp.status().is_success() {
            return Err(PortError::Upstream(format!("clv status={}", resp.status())));
        }
        let parsed: serde_json::Value = resp.json().await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        let raw = parsed.pointer("/predictions/0")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| PortError::Upstream("missing clv prediction".into()))?;
        Clv::try_new(raw).map_err(|e| PortError::Upstream(e.to_string()))
    }
}
