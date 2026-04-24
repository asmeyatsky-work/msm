//! Vertex AI Feature Store online-serving adapter.
//! §3.1: no business logic; pure lookup + deserialization.

use crate::gcp_auth::MetadataTokenSource;
use async_trait::async_trait;
use msm_scoring_domain::ports::{FeatureOverrides, FeatureStore, PortError};
use std::sync::Arc;
use std::time::Duration;

pub struct VertexFeatureStore {
    http: reqwest::Client,
    tokens: Arc<MetadataTokenSource>,
    // e.g. projects/P/locations/L/featureOnlineStores/S/featureViews/V
    feature_view: String,
    api_root: String,
}

impl VertexFeatureStore {
    pub fn new(region: String, feature_view: String, per_call_timeout: Duration) -> Self {
        let http = reqwest::Client::builder()
            .timeout(per_call_timeout)
            .build()
            .expect("client");
        Self {
            http,
            tokens: Arc::new(MetadataTokenSource::new(per_call_timeout)),
            feature_view,
            api_root: format!("https://{region}-aiplatform.googleapis.com/v1"),
        }
    }
}

#[async_trait]
impl FeatureStore for VertexFeatureStore {
    async fn lookup(&self, click_id: &str) -> Result<FeatureOverrides, PortError> {
        let token = self.tokens.token().await.map_err(PortError::Upstream)?;
        let url = format!("{}/{}:fetchFeatureValues", self.api_root, self.feature_view);
        let body = serde_json::json!({
            "dataKey": { "key": click_id },
            "format": "KEY_VALUE",
        });
        let resp = self
            .http
            .post(url)
            .bearer_auth(token)
            .json(&body)
            .send()
            .await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        if !resp.status().is_success() {
            return Err(PortError::Upstream(format!("fs status={}", resp.status())));
        }
        let parsed: serde_json::Value = resp
            .json()
            .await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        let kv = parsed
            .pointer("/keyValues/features")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();
        let mut out = FeatureOverrides::default();
        for entry in kv {
            let name = entry.get("name").and_then(|v| v.as_str()).unwrap_or("");
            let v = entry.pointer("/value/doubleValue").and_then(|v| v.as_f64());
            match name {
                "rpc_7d" => out.rpc_7d = v,
                "rpc_14d" => out.rpc_14d = v,
                "rpc_30d" => out.rpc_30d = v,
                "visits_prev_30d" => out.visits_prev_30d = v.map(|x| x as u32),
                _ => {}
            }
        }
        Ok(out)
    }
}
