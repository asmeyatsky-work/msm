use async_trait::async_trait;
use tokio::sync::RwLock;
use msm_scoring_domain::{
    guardrails::KillSwitch,
    ports::{ConfigSource, PortError},
};

/// Runtime-mutable config pulled from Secret Manager / GCS config object.
/// §4: secrets never in env defaults; loaded at startup via Workload Identity.
/// PRD §5 Kill Switch: a flip of this in-memory cell is enough — no redeploy.
pub struct RuntimeConfig {
    inner: RwLock<Inner>,
}

struct Inner {
    kill: bool,
    bounds_min: f64,
    bounds_max: f64,
}

impl RuntimeConfig {
    pub fn new(kill: bool, bounds_min: f64, bounds_max: f64) -> Self {
        Self { inner: RwLock::new(Inner { kill, bounds_min, bounds_max }) }
    }
    pub async fn set_kill(&self, kill: bool) {
        self.inner.write().await.kill = kill;
    }
    pub async fn set_bounds(&self, min: f64, max: f64) {
        let mut g = self.inner.write().await;
        g.bounds_min = min; g.bounds_max = max;
    }
}

#[async_trait]
impl ConfigSource for RuntimeConfig {
    async fn kill_switch(&self) -> Result<KillSwitch, PortError> {
        Ok(KillSwitch::new(self.inner.read().await.kill))
    }
    async fn bounds(&self) -> Result<(f64, f64), PortError> {
        let g = self.inner.read().await;
        Ok((g.bounds_min, g.bounds_max))
    }
}
