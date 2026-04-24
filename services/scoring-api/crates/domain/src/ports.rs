//! Ports — §3.2: every external dependency has a port; adapters implement it;
//! tests use in-memory adapters. No SDKs imported here.

use async_trait::async_trait;
use crate::click::ClickFeatures;
use crate::prediction::{Rpc};
use crate::guardrails::KillSwitch;
use crate::clv::Clv;

#[derive(Debug, thiserror::Error)]
pub enum PortError {
    #[error("timeout after {0}ms")] Timeout(u64),
    #[error("upstream error: {0}")] Upstream(String),
    #[error("config missing: {0}")] MissingConfig(String),
}

/// Vertex AI endpoint (or any model host). Adapter lives in `infrastructure`.
#[async_trait]
pub trait ModelEndpoint: Send + Sync {
    async fn predict(&self, features: &ClickFeatures) -> Result<(Rpc, String), PortError>;
}

/// PRD §5 Circuit Breaker fallback path — real data-layer revenue lookup.
#[async_trait]
pub trait DataLayerRevenue: Send + Sync {
    async fn lookup(&self, features: &ClickFeatures) -> Result<Rpc, PortError>;
}

/// CLV model endpoint — PRD §6 "Hero" feature. Runs concurrently with the RPC
/// model on the hot path (§3.6); failures degrade gracefully.
#[async_trait]
pub trait ClvEndpoint: Send + Sync {
    async fn predict(&self, features: &ClickFeatures) -> Result<Clv, PortError>;
}

/// Feature Store (PRD §2.2): online lookup of rolling RPC + session signals
/// by click_id. Returns optional overrides; the use case merges them into the
/// ClickFeatures. Never a blocker — failure degrades to request-body features.
#[async_trait]
pub trait FeatureStore: Send + Sync {
    async fn lookup(&self, click_id: &str) -> Result<FeatureOverrides, PortError>;
}

#[derive(Debug, Clone, Default)]
pub struct FeatureOverrides {
    pub rpc_7d: Option<f64>,
    pub rpc_14d: Option<f64>,
    pub rpc_30d: Option<f64>,
    pub visits_prev_30d: Option<u32>,
}

/// Injected clock so domain/application remain pure and testable.
pub trait Clock: Send + Sync {
    fn now_epoch_ms(&self) -> u64;
}

/// Kill switch and bounds are config-sourced (§5: "without code deployment").
#[async_trait]
pub trait ConfigSource: Send + Sync {
    async fn kill_switch(&self) -> Result<KillSwitch, PortError>;
    async fn bounds(&self) -> Result<(f64, f64), PortError>;
    /// PRD §4.3 staged activation ratio in basis points (0..=10_000).
    /// Default impl returns 10_000 (100%) so existing adapters keep working.
    async fn canary_ratio_bp(&self) -> Result<u16, PortError> { Ok(10_000) }
}

/// §4: every write emits an audit event; append-only sink.
#[async_trait]
pub trait AuditSink: Send + Sync {
    async fn record(&self, event: AuditEvent) -> Result<(), PortError>;
}

/// Shadow Production sink (PRD §4.2) — append-only log of every prediction,
/// including fallbacks, so a reconciliation job can grade quality vs. realized
/// revenue without affecting bidding.
#[async_trait]
pub trait PredictionSink: Send + Sync {
    async fn record(&self, record: PredictionRecord) -> Result<(), PortError>;
}

#[derive(Debug, Clone)]
pub struct PredictionRecord {
    pub click_id: String,
    pub correlation_id: String,
    pub predicted_rpc: f64,
    pub source: &'static str,
    pub model_version: String,
    pub ts_ms: u64,
}

/// Model explanations endpoint (Vertex AI `:explain`). Distinct from `predict`
/// because it is latency-expensive and not on the hot path.
#[async_trait]
pub trait ExplainEndpoint: Send + Sync {
    async fn explain(&self, features: &ClickFeatures) -> Result<Attribution, PortError>;
}

/// Per-feature SHAP attribution returned by the explain port. Domain value object.
#[derive(Debug, Clone)]
pub struct Attribution {
    pub base_value: f64,
    pub contributions: Vec<(String, f64)>,
}

impl Attribution {
    /// Sorted (descending by |contribution|) top-k features.
    pub fn top_features(&self, k: usize) -> Vec<(&str, f64)> {
        let mut v: Vec<(&str, f64)> = self.contributions.iter()
            .map(|(k, v)| (k.as_str(), *v)).collect();
        v.sort_by(|a, b| b.1.abs().partial_cmp(&a.1.abs()).unwrap_or(std::cmp::Ordering::Equal));
        v.truncate(k);
        v
    }
}

#[derive(Debug, Clone)]
pub struct AuditEvent {
    pub actor: String,
    pub action: String,
    pub correlation_id: String,
    pub click_id: String,
    pub before_hash: Option<String>,
    pub after_hash: String,
    pub source: &'static str,
}
