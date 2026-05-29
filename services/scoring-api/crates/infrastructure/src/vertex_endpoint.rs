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
        // _FEATURE_ORDER). CC schema (PRD V2 §7.1):
        //   hour_of_day, affinity_score, rpc_14d, rpc_60d,
        //   prior_applicant, auction_pressure, visits_prev_30d,
        //   phoebe_calculator_used, phoebe_guides_read,
        //   phoebe_cards_compared, phoebe_session_engagement_s
        let body = serde_json::json!({
            "instances": [[
                features.hour_of_day() as f64,
                features.affinity_score(),
                features.rpc_14d(),
                features.rpc_60d(),
                if features.prior_applicant() { 1.0 } else { 0.0 },
                features.auction_pressure(),
                features.visits_prev_30d() as f64,
                if features.phoebe_calculator_used() { 1.0 } else { 0.0 },
                features.phoebe_guides_read() as f64,
                features.phoebe_cards_compared() as f64,
                features.phoebe_session_engagement_s(),
            ]]
        });
        let resp = self
            .http
            .post(&self.endpoint_url)
            .bearer_auth(token)
            .json(&body)
            .send()
            .await
            .map_err(|e| PortError::Upstream(crate::error::reqwest_chain("vertex send", &e)))?;
        let status = resp.status();
        let bytes = resp
            .bytes()
            .await
            .map_err(|e| PortError::Upstream(crate::error::reqwest_chain("vertex body", &e)))?;
        if !status.is_success() {
            return Err(PortError::Upstream(format!(
                "vertex status={} body={}",
                status,
                crate::error::snippet(&bytes)
            )));
        }
        let parsed: serde_json::Value = serde_json::from_slice(&bytes).map_err(|e| {
            PortError::Upstream(format!(
                "vertex json decode: {} (body={})",
                e,
                crate::error::snippet(&bytes)
            ))
        })?;
        // Vertex AI returns {"predictions": [x]} for a regression endpoint.
        let raw = parsed
            .pointer("/predictions/0")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| PortError::Upstream("missing predictions[0]".into()))?;
        // Prefer the model version that actually served this request — Vertex
        // includes `modelDisplayName` + `modelVersionId` on every response.
        // Fall back to the boot-time `model_version` if the response omits it
        // (e.g. older serving containers, local stubs).
        let resolved_version = match (
            parsed.get("modelDisplayName").and_then(|v| v.as_str()),
            parsed.get("modelVersionId").and_then(|v| v.as_str()),
        ) {
            (Some(name), Some(ver)) => format!("{name}@{ver}"),
            _ => self.model_version.clone(),
        };
        // XGBoost regression has no non-negativity constraint, so out-of-
        // distribution inputs can produce small negative predictions. RPC is
        // physical revenue (≥0 by definition); clamp and let PredictionBounds
        // handle the "is this plausible?" question. Without this clamp the
        // domain refuses to construct Rpc and the breaker opens.
        let clamped = raw.max(0.0);
        let rpc = Rpc::try_new(clamped).map_err(|e| PortError::Upstream(e.to_string()))?;
        Ok((rpc, resolved_version))
    }
}
