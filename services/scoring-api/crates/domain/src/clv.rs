//! CLV-adjusted bid premium — PRD §6 "Hero Feature".
//! Pure domain rule; isolates the bidding economics from the model I/O.

use crate::errors::DomainError;
use crate::prediction::Rpc;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, PartialOrd, Serialize, Deserialize)]
pub struct Clv(f64);

impl Clv {
    pub fn try_new(v: f64) -> Result<Self, DomainError> {
        if v.is_nan() || v.is_infinite() || v < 0.0 {
            return Err(DomainError::InvalidRpc(format!("clv={v}")));
        }
        Ok(Self(v))
    }
    pub fn value(self) -> f64 {
        self.0
    }
}

/// Premium policy. The economic choice (how aggressively to steer spend toward
/// high-CLV users) is captured here, not in adapters — §3.1, §7.2.
///
/// Formula: `rpc_adjusted = rpc * (1 + alpha * min(clv / clv_reference, cap))`
/// - `alpha` — how much weight CLV has relative to immediate RPC
/// - `clv_reference` — normalization constant (e.g., median CLV)
/// - `cap` — hard ceiling so a single spectacular CLV doesn't blow up the bid
#[derive(Debug, Clone, Copy)]
pub struct ClvPremium {
    alpha: f64,
    clv_reference: f64,
    cap: f64,
}

impl ClvPremium {
    pub fn try_new(alpha: f64, clv_reference: f64, cap: f64) -> Result<Self, DomainError> {
        for (n, v) in [
            ("alpha", alpha),
            ("clv_reference", clv_reference),
            ("cap", cap),
        ] {
            if v.is_nan() || v.is_infinite() || v <= 0.0 {
                return Err(DomainError::InvalidRpc(format!("{n}={v}")));
            }
        }
        Ok(Self {
            alpha,
            clv_reference,
            cap,
        })
    }

    pub fn adjust(&self, rpc: Rpc, clv: Clv) -> Rpc {
        let ratio = (clv.value() / self.clv_reference).min(self.cap);
        let adjusted = rpc.value() * (1.0 + self.alpha * ratio);
        // Never negative by construction; unwrap is safe.
        Rpc::try_new(adjusted).unwrap_or(rpc)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_clv_returns_unchanged_rpc() {
        let p = ClvPremium::try_new(0.5, 100.0, 3.0).unwrap();
        let out = p.adjust(Rpc::try_new(2.0).unwrap(), Clv::try_new(0.0).unwrap());
        assert!((out.value() - 2.0).abs() < 1e-9);
    }

    #[test]
    fn clv_at_reference_applies_alpha() {
        let p = ClvPremium::try_new(0.5, 100.0, 3.0).unwrap();
        let out = p.adjust(Rpc::try_new(2.0).unwrap(), Clv::try_new(100.0).unwrap());
        assert!((out.value() - 3.0).abs() < 1e-9); // 2.0 * (1 + 0.5 * 1.0)
    }

    #[test]
    fn cap_prevents_runaway() {
        let p = ClvPremium::try_new(0.5, 100.0, 3.0).unwrap();
        // clv/ref = 10, but cap = 3
        let out = p.adjust(Rpc::try_new(1.0).unwrap(), Clv::try_new(1000.0).unwrap());
        assert!((out.value() - 2.5).abs() < 1e-9); // 1.0 * (1 + 0.5 * 3.0)
    }

    #[test]
    fn rejects_bad_params() {
        assert!(ClvPremium::try_new(-1.0, 100.0, 3.0).is_err());
        assert!(ClvPremium::try_new(0.5, 0.0, 3.0).is_err());
        assert!(ClvPremium::try_new(0.5, 100.0, 0.0).is_err());
    }
}
