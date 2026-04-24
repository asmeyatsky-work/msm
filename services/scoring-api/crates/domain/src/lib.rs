//! # Scoring Domain
//!
//! Layer: domain (Architectural Rules §2)
//! Ports: `ModelEndpoint`, `DataLayerRevenue`, `Clock`, `AuditSink`, `ConfigSource`
//! MCP integration: consumed by `mcp-servers/scoring-mcp` via the application layer.
//! Stack: Rust — canonical per §1 (p99 < 50ms hot path).
//!
//! This crate imports nothing beyond `std`, `thiserror`, `serde`, `async-trait`.
//! Rule §3.1: no business logic in adapters. All guardrail logic lives here.

#![forbid(unsafe_code)]

pub mod click;
pub mod prediction;
pub mod guardrails;
pub mod clv;
pub mod ports;
pub mod errors;

pub use click::{ClickFeatures, ClickId, CorrelationId};
pub use prediction::{Prediction, PredictionSource, Rpc};
pub use guardrails::{PredictionBounds, KillSwitch, CircuitBreakerState, AnomalyWindow};
pub use clv::{Clv, ClvPremium};
pub use errors::DomainError;
