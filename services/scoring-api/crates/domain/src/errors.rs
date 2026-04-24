use thiserror::Error;

#[derive(Debug, Error, PartialEq, Eq, Clone)]
pub enum DomainError {
    #[error("invalid hour_of_day: {0} (expected 0..=23)")]
    InvalidHour(i32),
    #[error("invalid cerberus_score: {0} (expected 0.0..=1.0)")]
    InvalidCerberusScore(String),
    #[error("invalid rpc value: {0}")]
    InvalidRpc(String),
    #[error("click_id must be non-empty")]
    EmptyClickId,
    #[error("bounds inverted: min {min} > max {max}")]
    BoundsInverted { min: String, max: String },
}
