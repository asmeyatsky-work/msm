use crate::gcp_auth::MetadataTokenSource;
use async_trait::async_trait;
use msm_scoring_domain::{
    ports::{Attribution, ExplainEndpoint, PortError},
    ClickFeatures,
};
use std::sync::Arc;
use std::time::Duration;

/// Vertex AI `:explain` endpoint adapter. Returns per-feature attributions.
pub struct VertexExplain {
    http: reqwest::Client,
    endpoint_url: String,
    tokens: Arc<MetadataTokenSource>,
}

impl VertexExplain {
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
impl ExplainEndpoint for VertexExplain {
    async fn explain(&self, features: &ClickFeatures) -> Result<Attribution, PortError> {
        let token = self.tokens.token().await.map_err(PortError::Upstream)?;
        // Match VertexEndpoint payload shape: 2D numeric array, feature order
        // aligned with the trained model.
        let body = serde_json::json!({
            "instances": [[
                features.hour_of_day() as f64,
                features.cerberus_score(),
                features.rpc_7d(),
                features.rpc_14d(),
                features.rpc_30d(),
                if features.is_payday_week() { 1.0 } else { 0.0 },
                features.auction_pressure(),
                features.visits_prev_30d() as f64,
            ]]
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
            return Err(PortError::Upstream(format!(
                "explain status={}",
                resp.status()
            )));
        }
        let parsed: serde_json::Value = resp
            .json()
            .await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        // Vertex AI explain response shape:
        //   {"explanations":[{"attributions":[{"baselineOutputValue":..,
        //       "featureAttributions":{"name":val,...}}]}]}
        let attr = parsed
            .pointer("/explanations/0/attributions/0")
            .ok_or_else(|| PortError::Upstream("missing attributions[0]".into()))?;
        let base_value = attr
            .get("baselineOutputValue")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        let feats = attr
            .get("featureAttributions")
            .and_then(|v| v.as_object())
            .ok_or_else(|| PortError::Upstream("missing featureAttributions".into()))?;
        let contributions = feats
            .iter()
            .filter_map(|(k, v)| v.as_f64().map(|f| (k.clone(), f)))
            .collect();
        Ok(Attribution {
            base_value,
            contributions,
        })
    }
}
