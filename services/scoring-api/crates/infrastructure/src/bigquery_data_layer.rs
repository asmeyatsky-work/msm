use std::sync::Arc;
use std::time::Duration;
use async_trait::async_trait;
use msm_scoring_domain::{
    ClickFeatures, Rpc,
    ports::{DataLayerRevenue, PortError},
};
use crate::gcp_auth::MetadataTokenSource;

/// BigQuery `jobs.query` adapter for PRD §5 circuit-breaker fallback.
/// Runs a parameterized lookup on the sales ledger keyed on click_id.
pub struct BigQueryDataLayer {
    http: reqwest::Client,
    tokens: Arc<MetadataTokenSource>,
    project: String,
    dataset: String,
    table: String,
    timeout: Duration,
}

impl BigQueryDataLayer {
    pub fn new(project: String, dataset: String, table: String, per_call_timeout: Duration) -> Self {
        let http = reqwest::Client::builder().timeout(per_call_timeout).build().expect("client");
        Self {
            http,
            tokens: Arc::new(MetadataTokenSource::new(per_call_timeout)),
            project, dataset, table, timeout: per_call_timeout,
        }
    }
}

#[async_trait]
impl DataLayerRevenue for BigQueryDataLayer {
    async fn lookup(&self, features: &ClickFeatures) -> Result<Rpc, PortError> {
        let token = self.tokens.token().await.map_err(PortError::Upstream)?;
        let url = format!("https://bigquery.googleapis.com/bigquery/v2/projects/{}/queries", self.project);
        let sql = format!(
            "SELECT COALESCE(SUM(revenue), 0.0) AS v FROM `{}.{}.{}` WHERE click_id = @cid",
            self.project, self.dataset, self.table,
        );
        let body = serde_json::json!({
            "query": sql,
            "useLegacySql": false,
            "timeoutMs": self.timeout.as_millis() as u64,
            "parameterMode": "NAMED",
            "queryParameters": [{
                "name": "cid",
                "parameterType": {"type": "STRING"},
                "parameterValue": {"value": features.click_id().as_str()},
            }],
        });
        let resp = self.http.post(url).bearer_auth(token).json(&body).send().await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        if !resp.status().is_success() {
            return Err(PortError::Upstream(format!("bq status={}", resp.status())));
        }
        let parsed: serde_json::Value = resp.json().await
            .map_err(|e| PortError::Upstream(e.to_string()))?;
        // rows[0].f[0].v is the revenue value from `jobs.query`.
        let raw = parsed.pointer("/rows/0/f/0/v")
            .and_then(|v| v.as_str())
            .and_then(|s| s.parse::<f64>().ok())
            .unwrap_or(0.0);
        Rpc::try_new(raw).map_err(|e| PortError::Upstream(e.to_string()))
    }
}
