//! Click value objects. Immutable; invariants enforced in constructors (§3.3, §3.4).

use crate::errors::DomainError;
use serde::{Deserialize, Serialize};

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
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct CorrelationId(String);

impl CorrelationId {
    pub fn new(raw: impl Into<String>) -> Self {
        Self(raw.into())
    }
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// Validated, immutable click feature vector. Constructed only via `try_new`,
/// which enforces every invariant (§3.4). Schema: PRD V2 §7.1 (Credit Cards).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClickFeatures {
    click_id: ClickId,
    correlation_id: CorrelationId,
    vertical_id: String,

    device: String,
    geo: String,
    hour_of_day: u8,
    product_type: String,
    card_product_id: String,
    query_intent: String,
    affinity_score: f64,
    ad_creative_id: String,
    prior_applicant: bool,
    income_band_bucket: Option<String>,

    auction_pressure: f64,

    rpc_14d: f64,
    rpc_60d: f64,

    landing_path: String,
    visits_prev_30d: u32,

    // Phoebe / GA4 behavioural features — PRD V2 §7.1 (Credit Cards).
    phoebe_calculator_used: bool,
    phoebe_guides_read: u32,
    phoebe_cards_compared: u32,
    phoebe_session_engagement_s: f64,
}

#[derive(Debug, Clone)]
pub struct ClickFeaturesInput {
    pub click_id: String,
    pub correlation_id: String,
    pub vertical_id: String,
    pub device: String,
    pub geo: String,
    pub hour_of_day: i32,
    pub product_type: String,
    pub card_product_id: String,
    pub query_intent: String,
    pub affinity_score: f64,
    pub ad_creative_id: String,
    pub prior_applicant: bool,
    pub income_band_bucket: Option<String>,
    pub auction_pressure: f64,
    pub rpc_14d: f64,
    pub rpc_60d: f64,
    pub landing_path: String,
    pub visits_prev_30d: u32,
    pub phoebe_calculator_used: bool,
    pub phoebe_guides_read: u32,
    pub phoebe_cards_compared: u32,
    pub phoebe_session_engagement_s: f64,
}

impl ClickFeatures {
    pub fn try_new(i: ClickFeaturesInput) -> Result<Self, DomainError> {
        if !(0..=23).contains(&i.hour_of_day) {
            return Err(DomainError::InvalidHour(i.hour_of_day));
        }
        if i.vertical_id.trim().is_empty() {
            return Err(DomainError::EmptyVerticalId);
        }
        if i.product_type.trim().is_empty() {
            return Err(DomainError::EmptyProductType);
        }
        if !(0.0..=1.0).contains(&i.affinity_score) || i.affinity_score.is_nan() {
            return Err(DomainError::InvalidAffinityScore(
                i.affinity_score.to_string(),
            ));
        }
        if !(0.0..=1.0).contains(&i.auction_pressure) || i.auction_pressure.is_nan() {
            return Err(DomainError::InvalidAuctionPressure(
                i.auction_pressure.to_string(),
            ));
        }
        for (name, v) in [("rpc_14d", i.rpc_14d), ("rpc_60d", i.rpc_60d)] {
            if v.is_nan() || v.is_infinite() || v < 0.0 {
                return Err(DomainError::InvalidRpc(format!("{name}={v}")));
            }
        }
        if i.phoebe_session_engagement_s.is_nan()
            || i.phoebe_session_engagement_s.is_infinite()
            || i.phoebe_session_engagement_s < 0.0
        {
            return Err(DomainError::InvalidPhoebeEngagement(
                i.phoebe_session_engagement_s.to_string(),
            ));
        }
        if let Some(ref b) = i.income_band_bucket {
            if !matches!(b.as_str(), "low" | "mid" | "high") {
                return Err(DomainError::InvalidIncomeBand(b.clone()));
            }
        }
        Ok(Self {
            click_id: ClickId::new(i.click_id)?,
            correlation_id: CorrelationId::new(i.correlation_id),
            vertical_id: i.vertical_id,
            device: i.device,
            geo: i.geo,
            hour_of_day: i.hour_of_day as u8,
            product_type: i.product_type,
            card_product_id: i.card_product_id,
            query_intent: i.query_intent,
            affinity_score: i.affinity_score,
            ad_creative_id: i.ad_creative_id,
            prior_applicant: i.prior_applicant,
            income_band_bucket: i.income_band_bucket,
            auction_pressure: i.auction_pressure,
            rpc_14d: i.rpc_14d,
            rpc_60d: i.rpc_60d,
            landing_path: i.landing_path,
            visits_prev_30d: i.visits_prev_30d,
            phoebe_calculator_used: i.phoebe_calculator_used,
            phoebe_guides_read: i.phoebe_guides_read,
            phoebe_cards_compared: i.phoebe_cards_compared,
            phoebe_session_engagement_s: i.phoebe_session_engagement_s,
        })
    }

    pub fn click_id(&self) -> &ClickId {
        &self.click_id
    }
    pub fn correlation_id(&self) -> &CorrelationId {
        &self.correlation_id
    }
    pub fn vertical_id(&self) -> &str {
        &self.vertical_id
    }
    pub fn product_type(&self) -> &str {
        &self.product_type
    }
    pub fn card_product_id(&self) -> &str {
        &self.card_product_id
    }
    pub fn query_intent(&self) -> &str {
        &self.query_intent
    }
    pub fn affinity_score(&self) -> f64 {
        self.affinity_score
    }
    pub fn prior_applicant(&self) -> bool {
        self.prior_applicant
    }
    pub fn income_band_bucket(&self) -> Option<&str> {
        self.income_band_bucket.as_deref()
    }
    pub fn rpc_14d(&self) -> f64 {
        self.rpc_14d
    }
    pub fn rpc_60d(&self) -> f64 {
        self.rpc_60d
    }
    pub fn visits_prev_30d(&self) -> u32 {
        self.visits_prev_30d
    }
    pub fn hour_of_day(&self) -> u8 {
        self.hour_of_day
    }
    pub fn auction_pressure(&self) -> f64 {
        self.auction_pressure
    }
    pub fn phoebe_calculator_used(&self) -> bool {
        self.phoebe_calculator_used
    }
    pub fn phoebe_guides_read(&self) -> u32 {
        self.phoebe_guides_read
    }
    pub fn phoebe_cards_compared(&self) -> u32 {
        self.phoebe_cards_compared
    }
    pub fn phoebe_session_engagement_s(&self) -> f64 {
        self.phoebe_session_engagement_s
    }

    /// Returns a new instance with fresh rolling signals (§3.3 immutable; state
    /// changes return new instances). NaN or negative overrides are ignored.
    #[must_use]
    pub fn with_overrides(mut self, o: &crate::ports::FeatureOverrides) -> Self {
        if let Some(v) = o.rpc_14d {
            if v.is_finite() && v >= 0.0 {
                self.rpc_14d = v;
            }
        }
        if let Some(v) = o.rpc_60d {
            if v.is_finite() && v >= 0.0 {
                self.rpc_60d = v;
            }
        }
        if let Some(v) = o.visits_prev_30d {
            self.visits_prev_30d = v;
        }
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_input() -> ClickFeaturesInput {
        ClickFeaturesInput {
            click_id: "c-1".into(),
            correlation_id: "t-1".into(),
            vertical_id: "credit_cards".into(),
            device: "mobile".into(),
            geo: "GB-LDN".into(),
            hour_of_day: 14,
            product_type: "cashback".into(),
            card_product_id: "card-amex-blue".into(),
            query_intent: "compare".into(),
            affinity_score: 0.7,
            ad_creative_id: "ad-1".into(),
            prior_applicant: false,
            income_band_bucket: Some("mid".into()),
            auction_pressure: 0.4,
            rpc_14d: 1.2,
            rpc_60d: 1.1,
            landing_path: "/credit-cards/cashback".into(),
            visits_prev_30d: 3,
            phoebe_calculator_used: true,
            phoebe_guides_read: 2,
            phoebe_cards_compared: 4,
            phoebe_session_engagement_s: 320.5,
        }
    }

    #[test]
    fn constructs_with_valid_input() {
        assert!(ClickFeatures::try_new(valid_input()).is_ok());
    }

    #[test]
    fn rejects_bad_hour() {
        let mut i = valid_input();
        i.hour_of_day = 24;
        assert!(matches!(
            ClickFeatures::try_new(i),
            Err(DomainError::InvalidHour(24))
        ));
    }

    #[test]
    fn rejects_bad_affinity() {
        let mut i = valid_input();
        i.affinity_score = 1.5;
        assert!(matches!(
            ClickFeatures::try_new(i),
            Err(DomainError::InvalidAffinityScore(_))
        ));
    }

    #[test]
    fn rejects_negative_rpc() {
        let mut i = valid_input();
        i.rpc_14d = -0.01;
        assert!(matches!(
            ClickFeatures::try_new(i),
            Err(DomainError::InvalidRpc(_))
        ));
    }

    #[test]
    fn rejects_empty_click_id() {
        let mut i = valid_input();
        i.click_id = "".into();
        assert!(matches!(
            ClickFeatures::try_new(i),
            Err(DomainError::EmptyClickId)
        ));
    }

    #[test]
    fn rejects_empty_vertical_id() {
        let mut i = valid_input();
        i.vertical_id = "".into();
        assert!(matches!(
            ClickFeatures::try_new(i),
            Err(DomainError::EmptyVerticalId)
        ));
    }

    #[test]
    fn rejects_unknown_income_band() {
        let mut i = valid_input();
        i.income_band_bucket = Some("vip".into());
        assert!(matches!(
            ClickFeatures::try_new(i),
            Err(DomainError::InvalidIncomeBand(_))
        ));
    }

    #[test]
    fn accepts_null_income_band() {
        let mut i = valid_input();
        i.income_band_bucket = None;
        assert!(ClickFeatures::try_new(i).is_ok());
    }

    #[test]
    fn rejects_negative_phoebe_engagement() {
        let mut i = valid_input();
        i.phoebe_session_engagement_s = -1.0;
        assert!(matches!(
            ClickFeatures::try_new(i),
            Err(DomainError::InvalidPhoebeEngagement(_))
        ));
    }
}
