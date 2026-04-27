//! PRD §5 Safety Guardrails — first-class domain logic.
//! All rules here are pure; §3.1 forbids business logic in adapters.

use crate::errors::DomainError;
use crate::prediction::Rpc;
use serde::{Deserialize, Serialize};

/// Hard min/max. Predictions outside are rejected in favor of tCPA fallback.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct PredictionBounds {
    min: f64,
    max: f64,
}

impl PredictionBounds {
    pub fn try_new(min: f64, max: f64) -> Result<Self, DomainError> {
        if min.is_nan() || max.is_nan() || min < 0.0 || max < 0.0 {
            return Err(DomainError::InvalidRpc(format!("min={min} max={max}")));
        }
        if min > max {
            return Err(DomainError::BoundsInverted {
                min: min.to_string(),
                max: max.to_string(),
            });
        }
        Ok(Self { min, max })
    }
    pub fn contains(&self, rpc: Rpc) -> bool {
        let v = rpc.value();
        v >= self.min && v <= self.max
    }
    pub fn min(&self) -> f64 {
        self.min
    }
    pub fn max(&self) -> f64 {
        self.max
    }
}

/// Single-config kill switch. PRD §5: "disable the feed instantly without code deployment."
#[derive(Debug, Clone, Copy)]
pub struct KillSwitch {
    engaged: bool,
}

impl KillSwitch {
    pub fn new(engaged: bool) -> Self {
        Self { engaged }
    }
    pub fn is_engaged(self) -> bool {
        self.engaged
    }
}

/// Circuit breaker state machine. Transitions are pure; timeouts are injected by the
/// application layer via the `Clock` port.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CircuitBreakerState {
    Closed,
    Open { opened_at_epoch_ms: u64 },
    HalfOpen,
}

impl CircuitBreakerState {
    pub fn allows_call(self, now_epoch_ms: u64, cool_off_ms: u64) -> bool {
        match self {
            CircuitBreakerState::Closed | CircuitBreakerState::HalfOpen => true,
            CircuitBreakerState::Open { opened_at_epoch_ms } => {
                now_epoch_ms.saturating_sub(opened_at_epoch_ms) >= cool_off_ms
            }
        }
    }
}

/// Null/zero rate window. PRD §5: ">3% triggers the breaker".
///
/// Sliding time window: only samples within `window_ms` of `now_ms` count
/// toward the ratio. A `min_samples` floor prevents one zero in five from
/// tripping the breaker at low traffic. Once the window ages out the offending
/// samples, `breached()` recovers — the cumulative-counter prior version
/// stayed breached forever after the first trip.
#[derive(Debug, Clone)]
pub struct AnomalyWindow {
    threshold: f64,
    window_ms: u64,
    min_samples: u64,
    samples: std::collections::VecDeque<(u64, bool)>,
}

impl AnomalyWindow {
    pub fn new(threshold: f64, window_ms: u64, min_samples: u64) -> Self {
        Self {
            threshold,
            window_ms,
            min_samples,
            samples: std::collections::VecDeque::new(),
        }
    }

    pub fn record(&mut self, rpc: Rpc, now_ms: u64) {
        let cutoff = now_ms.saturating_sub(self.window_ms);
        while matches!(self.samples.front(), Some((t, _)) if *t < cutoff) {
            self.samples.pop_front();
        }
        self.samples.push_back((now_ms, rpc.value() == 0.0));
    }

    pub fn breached(&self) -> bool {
        let n = self.samples.len() as u64;
        if n < self.min_samples {
            return false;
        }
        let zeros = self.samples.iter().filter(|(_, z)| *z).count() as f64;
        zeros / n as f64 > self.threshold
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounds_reject_out_of_range() {
        let b = PredictionBounds::try_new(0.5, 10.0).unwrap();
        assert!(!b.contains(Rpc::try_new(0.0).unwrap()));
        assert!(b.contains(Rpc::try_new(5.0).unwrap()));
        assert!(!b.contains(Rpc::try_new(10.01).unwrap()));
    }

    #[test]
    fn bounds_reject_inverted() {
        assert!(PredictionBounds::try_new(10.0, 5.0).is_err());
    }

    #[test]
    fn breaker_open_blocks_until_cooloff() {
        let s = CircuitBreakerState::Open {
            opened_at_epoch_ms: 1000,
        };
        assert!(!s.allows_call(1500, 1000));
        assert!(s.allows_call(2001, 1000));
    }

    #[test]
    fn anomaly_window_breach_at_3_percent() {
        let mut w = AnomalyWindow::new(0.03, 60_000, 20);
        for _ in 0..97 {
            w.record(Rpc::try_new(1.0).unwrap(), 1_000);
        }
        for _ in 0..4 {
            w.record(Rpc::try_new(0.0).unwrap(), 1_000);
        }
        assert!(w.breached());
    }

    #[test]
    fn anomaly_window_min_samples_floor() {
        let mut w = AnomalyWindow::new(0.03, 60_000, 20);
        for _ in 0..3 {
            w.record(Rpc::try_new(0.0).unwrap(), 1_000);
        }
        assert!(!w.breached(), "below min_samples must not trip");
    }

    #[test]
    fn anomaly_window_recovers_after_window_ages_out() {
        let mut w = AnomalyWindow::new(0.03, 60_000, 20);
        // Fill the window with zeros at t=0 — clearly breached.
        for _ in 0..50 {
            w.record(Rpc::try_new(0.0).unwrap(), 0);
        }
        assert!(w.breached());
        // Push enough non-zeros far enough in the future that the zeros age out.
        for _ in 0..50 {
            w.record(Rpc::try_new(1.0).unwrap(), 120_000);
        }
        assert!(
            !w.breached(),
            "sliding window must drop aged samples and recover"
        );
    }
}
