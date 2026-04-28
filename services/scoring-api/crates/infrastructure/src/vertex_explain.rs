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
        // Vertex AI explain response. Two shapes are seen in the wild:
        //   (A) per-feature scalars (one named input per feature):
        //       "featureAttributions": {"hour_of_day": 0.3, "rpc_7d": 1.2, ...}
        //   (B) one named input ("features") with `index_feature_mapping`,
        //       attributions returned as a parallel array:
        //       "featureAttributions": {"features": [0.3, 1.2, ...]}
        // The deployed `rpc-estimator` model uses shape (B); we still accept
        // (A) so the integration tests' fake Vertex stays valid.
        const FEATURE_NAMES: [&str; 8] = [
            "hour_of_day",
            "cerberus_score",
            "rpc_7d",
            "rpc_14d",
            "rpc_30d",
            "is_payday_week",
            "auction_pressure",
            "visits_prev_30d",
        ];
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
        let contributions: Vec<(String, f64)> =
            if let Some(arr) = feats.values().next().and_then(|v| v.as_array()) {
                FEATURE_NAMES
                    .iter()
                    .zip(arr.iter())
                    .filter_map(|(name, v)| v.as_f64().map(|f| ((*name).to_string(), f)))
                    .collect()
            } else {
                feats
                    .iter()
                    .filter_map(|(k, v)| v.as_f64().map(|f| (k.clone(), f)))
                    .collect()
            };
        Ok(Attribution {
            base_value,
            contributions,
        })
    }
}
