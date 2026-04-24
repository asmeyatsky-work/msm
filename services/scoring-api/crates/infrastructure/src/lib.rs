//! # Scoring Infrastructure
//!
//! Layer: infrastructure (Architectural Rules §2).
//! Ports: implements `ModelEndpoint` (Vertex AI), `DataLayerRevenue` (BigQuery),
//! `Clock` (system), `ConfigSource` (Secret Manager + runtime config), `AuditSink`
//! (Pub/Sub append-only topic).
//! MCP integration: none directly; wired into the MCP server by `presentation`.
//! Stack: Rust (hot path).
//!
//! §3.1: no business logic. §4: Secret Manager + Workload Identity for secrets;
//! no env-var defaults for secrets. All outbound calls carry explicit timeouts.

#![forbid(unsafe_code)]

pub mod gcp_auth;
pub mod vertex_endpoint;
pub mod vertex_explain;
pub mod vertex_clv;
pub mod vertex_feature_store;
pub mod bigquery_data_layer;
pub mod system_clock;
pub mod runtime_config;
pub mod secret_manager_config;
pub mod pubsub_audit;
pub mod pubsub_predictions;

pub use vertex_endpoint::VertexEndpoint;
pub use vertex_explain::VertexExplain;
pub use vertex_clv::VertexClvEndpoint;
pub use vertex_feature_store::VertexFeatureStore;
pub use bigquery_data_layer::BigQueryDataLayer;
pub use system_clock::SystemClock;
pub use runtime_config::RuntimeConfig;
pub use secret_manager_config::SecretManagerConfig;
pub use pubsub_audit::PubSubAudit;
pub use pubsub_predictions::PubSubPredictions;
