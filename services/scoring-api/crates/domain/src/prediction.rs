use crate::click::{ClickId, CorrelationId};
use crate::errors::DomainError;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, PartialOrd, Serialize, Deserialize)]
pub struct Rpc(f64);

impl Rpc {
    pub fn try_new(v: f64) -> Result<Self, DomainError> {
        if v.is_nan() || v.is_infinite() || v < 0.0 {
            return Err(DomainError::InvalidRpc(v.to_string()));
        }
        Ok(Self(v))
    }
    pub fn value(self) -> f64 {
        self.0
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PredictionSource {
    Model,
    FallbackTcpa,      // bounds rejected — PRD §5 Prediction Bounds
    FallbackDataLayer, // circuit breaker open — PRD §5 Circuit Breaker
    KillSwitch,        // PRD §5 Kill Switch
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Prediction {
    click_id: ClickId,
    correlation_id: CorrelationId,
    rpc: Rpc,
    source: PredictionSource,
    model_version: String,
}

impl Prediction {
    pub fn new(
        click_id: ClickId,
        correlation_id: CorrelationId,
        rpc: Rpc,
        source: PredictionSource,
        model_version: impl Into<String>,
    ) -> Self {
        Self {
            click_id,
            correlation_id,
            rpc,
            source,
            model_version: model_version.into(),
        }
    }
    pub fn click_id(&self) -> &ClickId {
        &self.click_id
    }
    pub fn correlation_id(&self) -> &CorrelationId {
        &self.correlation_id
    }
    pub fn rpc(&self) -> Rpc {
        self.rpc
    }
    pub fn source(&self) -> PredictionSource {
        self.source
    }
    pub fn model_version(&self) -> &str {
        &self.model_version
    }
}
