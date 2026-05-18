use thiserror::Error;

#[derive(Debug, Error, PartialEq, Eq, Clone)]
pub enum DomainError {
    #[error("invalid hour_of_day: {0} (expected 0..=23)")]
    InvalidHour(i32),
    #[error("invalid affinity_score: {0} (expected 0.0..=1.0)")]
    InvalidAffinityScore(String),
    #[error("invalid auction_pressure: {0} (expected 0.0..=1.0)")]
    InvalidAuctionPressure(String),
    #[error("invalid rpc value: {0}")]
    InvalidRpc(String),
    #[error("click_id must be non-empty")]
    EmptyClickId,
    #[error("vertical_id must be non-empty")]
    EmptyVerticalId,
    #[error("product_type must be non-empty")]
    EmptyProductType,
    #[error("invalid income_band_bucket: {0} (expected low|mid|high|null)")]
    InvalidIncomeBand(String),
    #[error("invalid phoebe_session_engagement_s: {0} (expected non-negative finite)")]
    InvalidPhoebeEngagement(String),
    #[error("bounds inverted: min {min} > max {max}")]
    BoundsInverted { min: String, max: String },
}
