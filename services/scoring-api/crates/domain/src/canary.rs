//! Staged activation sampler — PRD §4.3.
//!
//! The sampler is a pure domain rule: hash(click_id) mod 10000 < ratio_bp.
//! Stickiness matters — the *same* click must always receive the same decision
//! across retries or re-scores, so reconciliation compares like to like.
//!
//! Kept separate from guardrails: a click can be rejected by bounds/killswitch
//! AND be in-canary; the guardrail decision wins because it's about safety,
//! the canary decision is about rollout staging.

use crate::click::ClickId;
use crate::errors::DomainError;

/// Activation ratio in basis points (0..=10_000 = 0%..=100%).
/// PRD §4.3 bands: 100 (1%), 1000 (10%), 5000 (50%), 10000 (100%).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CanaryRatio(u16);

impl CanaryRatio {
    pub fn try_new(bp: u16) -> Result<Self, DomainError> {
        if bp > 10_000 {
            return Err(DomainError::InvalidRpc(format!("canary bp={bp} >10000")));
        }
        Ok(Self(bp))
    }
    pub fn full() -> Self { Self(10_000) }
    pub fn off()  -> Self { Self(0) }
    pub fn as_bp(self) -> u16 { self.0 }
}

/// Deterministic FNV-1a 64-bit — no external dep, keeps domain free of SDKs (§2).
fn fnv1a(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in bytes {
        h ^= *b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

pub struct CanarySampler { ratio: CanaryRatio }

impl CanarySampler {
    pub fn new(ratio: CanaryRatio) -> Self { Self { ratio } }

    /// `true` → expose the model prediction to bidding.
    /// `false` → treat this click as out-of-canary (caller should use tCPA fallback).
    pub fn in_canary(&self, click_id: &ClickId) -> bool {
        if self.ratio.as_bp() == 0 { return false; }
        if self.ratio.as_bp() == 10_000 { return true; }
        let bucket = (fnv1a(click_id.as_str().as_bytes()) % 10_000) as u16;
        bucket < self.ratio.as_bp()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cid(s: &str) -> ClickId { ClickId::new(s).unwrap() }

    #[test]
    fn full_ratio_includes_everything() {
        let s = CanarySampler::new(CanaryRatio::full());
        for i in 0..100 {
            assert!(s.in_canary(&cid(&format!("c-{i}"))));
        }
    }

    #[test]
    fn zero_ratio_excludes_everything() {
        let s = CanarySampler::new(CanaryRatio::off());
        for i in 0..100 {
            assert!(!s.in_canary(&cid(&format!("c-{i}"))));
        }
    }

    #[test]
    fn decision_is_sticky() {
        let s = CanarySampler::new(CanaryRatio::try_new(100).unwrap());
        let c = cid("same-click");
        let first = s.in_canary(&c);
        for _ in 0..10 { assert_eq!(s.in_canary(&c), first); }
    }

    #[test]
    fn sampling_is_approximately_uniform() {
        // With 10% target on 5_000 clicks, expect ~500 ± wide margin.
        let s = CanarySampler::new(CanaryRatio::try_new(1_000).unwrap());
        let hits = (0..5000).filter(|i| s.in_canary(&cid(&format!("c-{i}")))).count();
        assert!((350..650).contains(&hits), "got {hits} in canary (expected ~500)");
    }

    #[test]
    fn rejects_out_of_range_ratio() {
        assert!(CanaryRatio::try_new(10_001).is_err());
    }
}
