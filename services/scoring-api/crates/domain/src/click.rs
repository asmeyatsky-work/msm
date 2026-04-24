//! Click value objects. Immutable; invariants enforced in constructors (§3.3, §3.4).

use serde::{Deserialize, Serialize};
use crate::errors::DomainError;

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ClickId(String);

impl ClickId {
    pub fn new(raw: impl Into<String>) -> Result<Self, DomainError> {
        let s = raw.into();
        if s.trim().is_empty() {
            return Err(DomainError::EmptyClickId);
        }
        Ok(Self(s))
    }
    pub fn as_str(&self) -> &str { &self.0 }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CorrelationId(String);

impl CorrelationId {
    pub fn new(raw: impl Into<String>) -> Self { Self(raw.into()) }
    pub fn as_str(&self) -> &str { &self.0 }
}

/// Validated, immutable click feature vector. Constructed only via `try_new`,
/// which enforces every invariant (§3.4). PRD §3.1 feature inventory.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClickFeatures {
    click_id: ClickId,
    correlation_id: CorrelationId,

    device: String,
    geo: String,
    hour_of_day: u8,
    query_intent: String,
    ad_creative_id: String,
    cerberus_score: f64,

    rpc_7d: f64,
    rpc_14d: f64,
    rpc_30d: f64,

    is_payday_week: bool,
    auction_pressure: f64,

    landing_path: String,
    visits_prev_30d: u32,
}

#[derive(Debug, Clone)]
pub struct ClickFeaturesInput {
    pub click_id: String,
    pub correlation_id: String,
    pub device: String,
    pub geo: String,
    pub hour_of_day: i32,
    pub query_intent: String,
    pub ad_creative_id: String,
    pub cerberus_score: f64,
    pub rpc_7d: f64,
    pub rpc_14d: f64,
    pub rpc_30d: f64,
    pub is_payday_week: bool,
    pub auction_pressure: f64,
    pub landing_path: String,
    pub visits_prev_30d: u32,
}

impl ClickFeatures {
    pub fn try_new(i: ClickFeaturesInput) -> Result<Self, DomainError> {
        if !(0..=23).contains(&i.hour_of_day) {
            return Err(DomainError::InvalidHour(i.hour_of_day));
        }
        if !(0.0..=1.0).contains(&i.cerberus_score) || i.cerberus_score.is_nan() {
            return Err(DomainError::InvalidCerberusScore(i.cerberus_score.to_string()));
        }
        for (name, v) in [("rpc_7d", i.rpc_7d), ("rpc_14d", i.rpc_14d), ("rpc_30d", i.rpc_30d)] {
            if v.is_nan() || v.is_infinite() || v < 0.0 {
                return Err(DomainError::InvalidRpc(format!("{name}={v}")));
            }
        }
        Ok(Self {
            click_id: ClickId::new(i.click_id)?,
            correlation_id: CorrelationId::new(i.correlation_id),
            device: i.device,
            geo: i.geo,
            hour_of_day: i.hour_of_day as u8,
            query_intent: i.query_intent,
            ad_creative_id: i.ad_creative_id,
            cerberus_score: i.cerberus_score,
            rpc_7d: i.rpc_7d,
            rpc_14d: i.rpc_14d,
            rpc_30d: i.rpc_30d,
            is_payday_week: i.is_payday_week,
            auction_pressure: i.auction_pressure,
            landing_path: i.landing_path,
            visits_prev_30d: i.visits_prev_30d,
        })
    }

    pub fn click_id(&self) -> &ClickId { &self.click_id }
    pub fn correlation_id(&self) -> &CorrelationId { &self.correlation_id }
    pub fn cerberus_score(&self) -> f64 { self.cerberus_score }
    pub fn rpc_7d(&self) -> f64 { self.rpc_7d }
    pub fn rpc_14d(&self) -> f64 { self.rpc_14d }
    pub fn rpc_30d(&self) -> f64 { self.rpc_30d }
    pub fn visits_prev_30d(&self) -> u32 { self.visits_prev_30d }

    /// Returns a new instance with fresh rolling signals (§3.3 immutable; state
    /// changes return new instances). NaN or negative overrides are ignored.
    #[must_use]
    pub fn with_overrides(mut self, o: &crate::ports::FeatureOverrides) -> Self {
        if let Some(v) = o.rpc_7d   { if v.is_finite() && v >= 0.0 { self.rpc_7d  = v; } }
        if let Some(v) = o.rpc_14d  { if v.is_finite() && v >= 0.0 { self.rpc_14d = v; } }
        if let Some(v) = o.rpc_30d  { if v.is_finite() && v >= 0.0 { self.rpc_30d = v; } }
        if let Some(v) = o.visits_prev_30d { self.visits_prev_30d = v; }
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_input() -> ClickFeaturesInput {
        ClickFeaturesInput {
            click_id: "c-1".into(), correlation_id: "t-1".into(),
            device: "mobile".into(), geo: "US-CA".into(), hour_of_day: 14,
            query_intent: "commercial".into(), ad_creative_id: "ad-1".into(),
            cerberus_score: 0.8, rpc_7d: 1.2, rpc_14d: 1.1, rpc_30d: 1.0,
            is_payday_week: false, auction_pressure: 0.4,
            landing_path: "/p".into(), visits_prev_30d: 3,
        }
    }

    #[test]
    fn constructs_with_valid_input() {
        assert!(ClickFeatures::try_new(valid_input()).is_ok());
    }

    #[test]
    fn rejects_bad_hour() {
        let mut i = valid_input(); i.hour_of_day = 24;
        assert!(matches!(ClickFeatures::try_new(i), Err(DomainError::InvalidHour(24))));
    }

    #[test]
    fn rejects_bad_cerberus() {
        let mut i = valid_input(); i.cerberus_score = 1.5;
        assert!(matches!(ClickFeatures::try_new(i), Err(DomainError::InvalidCerberusScore(_))));
    }

    #[test]
    fn rejects_negative_rpc() {
        let mut i = valid_input(); i.rpc_7d = -0.01;
        assert!(matches!(ClickFeatures::try_new(i), Err(DomainError::InvalidRpc(_))));
    }

    #[test]
    fn rejects_empty_click_id() {
        let mut i = valid_input(); i.click_id = "".into();
        assert!(matches!(ClickFeatures::try_new(i), Err(DomainError::EmptyClickId)));
    }
}
