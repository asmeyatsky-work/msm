//! # Scoring Application
//!
//! Layer: application (Architectural Rules §2; imports only `domain`).
//! Ports: re-exports domain ports; injects concrete adapters at construction.
//! MCP integration: `mcp-servers/scoring-mcp` calls `ScoreClick` as a tool.
//! Stack: Rust (hot path).
//!
//! Orchestrates the PRD §5 guardrail decision tree on every click:
//!   kill switch → breaker → model call (timeout) → bounds check → audit.

#![forbid(unsafe_code)]

pub mod score_click;
pub mod explain_click;
pub use score_click::{ScoreClick, ScoreClickDeps, ScoreClickError};
pub use explain_click::{ExplainClick, ExplainClickError};
