use std::sync::Arc;
use std::time::Duration;
use tracing::instrument;
use msm_scoring_domain::{
    ClickFeatures,
    ports::{ExplainEndpoint, Attribution, PortError},
};

#[derive(Debug, thiserror::Error)]
pub enum ExplainClickError {
    #[error("explain failed: {0}")] Upstream(String),
    #[error("timeout")] Timeout,
}

pub struct ExplainClick {
    endpoint: Arc<dyn ExplainEndpoint>,
    timeout: Duration,
}

impl ExplainClick {
    pub fn new(endpoint: Arc<dyn ExplainEndpoint>, timeout: Duration) -> Self {
        Self { endpoint, timeout }
    }

    #[instrument(skip(self, features), fields(click_id = features.click_id().as_str()))]
    pub async fn execute(&self, features: ClickFeatures) -> Result<Attribution, ExplainClickError> {
        match tokio::time::timeout(self.timeout, self.endpoint.explain(&features)).await {
            Ok(Ok(a)) => Ok(a),
            Ok(Err(PortError::Timeout(_))) => Err(ExplainClickError::Timeout),
            Ok(Err(e)) => Err(ExplainClickError::Upstream(e.to_string())),
            Err(_) => Err(ExplainClickError::Timeout),
        }
    }
}
