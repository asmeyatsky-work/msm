use crate::gcp_auth::MetadataTokenSource;
use async_trait::async_trait;
use msm_scoring_domain::{
    ports::{ModelEndpoint, PortError},
    ClickFeatures, Rpc,
};
use std::sync::Arc;
use std::time::Duration;

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
        let http = reqwest::Client::builder()
            .timeout(per_call_timeout)
            .build()
            .expect("client");
        let tokens = Arc::new(MetadataTokenSource::new(per_call_timeout));
        Self {
            http,
            endpoint_url,
            model_version,
            tokens,
        }
    }
}

#[async_trait]
impl ModelEndpoint for VertexEndpoint {
    async fn predict(&self, features: &ClickFeatures) -> Result<(Rpc, String), PortError> {
        let token = self.tokens.token().await.map_err(PortError::Upstream)?;
        // Vertex AI prebuilt xgboost-cpu container expects a 2D numeric array.
        // Feature order MUST match training (see services/ml-pipeline/.../xgboost_trainer.py
        // _FEATURE_ORDER and ops/deploy_real_model.py feature_cols):
        //   hour_of_day, cerberus_score, rpc_7d, rpc_14d, rpc_30d,
        //   is_payday_week, auction_pressure, visits_prev_30d
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
            return Err(PortError::Upstream(format!("status={}", resp.status())));
        }
        let parsed: serde_json::Value = resp
            .json()
            .await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        // Vertex AI returns {"predictions": [x]} for a regression endpoint.
        let raw = parsed
            .pointer("/predictions/0")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| PortError::Upstream("missing predictions[0]".into()))?;
        // XGBoost regression has no non-negativity constraint, so out-of-
        // distribution inputs can produce small negative predictions. RPC is
        // physical revenue (≥0 by definition); clamp and let PredictionBounds
        // handle the "is this plausible?" question. Without this clamp the
        // domain refuses to construct Rpc and the breaker opens.
        let clamped = raw.max(0.0);
        let rpc = Rpc::try_new(clamped).map_err(|e| PortError::Upstream(e.to_string()))?;
        Ok((rpc, self.model_version.clone()))
    }
}
