use crate::gcp_auth::MetadataTokenSource;
use async_trait::async_trait;
use msm_scoring_domain::{
    ports::{ClvEndpoint, PortError},
    ClickFeatures, Clv,
};
use std::sync::Arc;
use std::time::Duration;

/// Vertex AI CLV prediction endpoint (PRD §6). Separate model from RPC.
pub struct VertexClvEndpoint {
    http: reqwest::Client,
    endpoint_url: String,
    tokens: Arc<MetadataTokenSource>,
}

impl VertexClvEndpoint {
    pub fn new(endpoint_url: String, per_call_timeout: Duration) -> Self {
        let http = reqwest::Client::builder()
            .timeout(per_call_timeout)
            .build()
            .expect("client");
        Self {
            http,
            endpoint_url,
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
                "vertical_id": features.vertical_id(),
                "product_type": features.product_type(),
                "affinity_score": features.affinity_score(),
                "rpc_14d": features.rpc_14d(),
                "rpc_60d": features.rpc_60d(),
                "prior_applicant": features.prior_applicant(),
            }]
        });
        let resp = self
            .http
            .post(&self.endpoint_url)
            .bearer_auth(token)
            .json(&body)
            .send()
            .await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        if !resp.status().is_success() {
            return Err(PortError::Upstream(format!("clv status={}", resp.status())));
        }
        let parsed: serde_json::Value = resp
            .json()
            .await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        let raw = parsed
            .pointer("/predictions/0")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| PortError::Upstream("missing clv prediction".into()))?;
        Clv::try_new(raw.max(0.0)).map_err(|e| PortError::Upstream(e.to_string()))
    }
}
