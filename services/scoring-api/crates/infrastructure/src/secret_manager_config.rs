//! Secret-Manager-backed ConfigSource. Polls the latest version on a background
//! refresh loop; `kill_switch()` returns the cached value so the hot path is
//! free of network I/O. Closes the PRD §5 auto-breaker loop with the
//! breaker-automation Cloud Function.

use async_trait::async_trait;
use serde::Deserialize;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;

use crate::gcp_auth::MetadataTokenSource;
use msm_scoring_domain::{
    guardrails::KillSwitch,
    ports::{ConfigSource, PortError},
};

#[derive(Debug, Clone, Deserialize)]
struct SecretPayload {
    #[serde(default)]
    kill: bool,
    #[serde(default = "default_min")]
    bounds_min: f64,
    #[serde(default = "default_max")]
    bounds_max: f64,
    /// PRD §4.3 staged activation ratio; default = 100%.
    #[serde(default = "default_canary_bp")]
    canary_bp: u16,
}
fn default_min() -> f64 { 0.01 }
fn default_max() -> f64 { 500.0 }
fn default_canary_bp() -> u16 { 10_000 }

pub struct SecretManagerConfig {
    cached: Arc<RwLock<SecretPayload>>,
}

impl SecretManagerConfig {
    /// Spawns a background refresh task. Returns once the first fetch succeeds
    /// so startup fails loud if Secret Manager / Workload Identity is broken.
    pub async fn new(
        project: String,
        secret_id: String,
        refresh_every: Duration,
        per_call_timeout: Duration,
    ) -> Result<Self, String> {
        let api_root = std::env::var("SECRETMANAGER_API_ROOT")
            .unwrap_or_else(|_| "https://secretmanager.googleapis.com".into());
        Self::with_api_root(api_root, project, secret_id, refresh_every, per_call_timeout).await
    }

    pub async fn with_api_root(
        api_root: String,
        project: String,
        secret_id: String,
        refresh_every: Duration,
        per_call_timeout: Duration,
    ) -> Result<Self, String> {
        let tokens = Arc::new(MetadataTokenSource::new(per_call_timeout));
        let http = reqwest::Client::builder()
            .timeout(per_call_timeout)
            .build()
            .map_err(|e| e.to_string())?;
        let url = format!(
            "{}/v1/projects/{}/secrets/{}/versions/latest:access",
            api_root, project, secret_id,
        );
        let initial = fetch(&http, &tokens, &url).await?;
        let cached = Arc::new(RwLock::new(initial));

        let cache_clone = Arc::clone(&cached);
        let http_clone = http.clone();
        let tokens_clone = Arc::clone(&tokens);
        let url_clone = url.clone();
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(refresh_every).await;
                match fetch(&http_clone, &tokens_clone, &url_clone).await {
                    Ok(p) => *cache_clone.write().await = p,
                    Err(e) => tracing::warn!(error = %e, "secret refresh failed"),
                }
            }
        });

        Ok(Self { cached })
    }
}

async fn fetch(
    http: &reqwest::Client,
    tokens: &MetadataTokenSource,
    url: &str,
) -> Result<SecretPayload, String> {
    let token = tokens.token().await?;
    let resp = http
        .get(url)
        .bearer_auth(token)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("secret status {}", resp.status()));
    }
    #[derive(Deserialize)]
    struct V {
        payload: P,
    }
    #[derive(Deserialize)]
    struct P {
        data: String,
    } // base64
    let v: V = resp.json().await.map_err(|e| e.to_string())?;
    let decoded = base64_decode(&v.payload.data)?;
    serde_json::from_slice(&decoded).map_err(|e| e.to_string())
}

fn base64_decode(s: &str) -> Result<Vec<u8>, String> {
    // Minimal url-safe + std base64 decoder to avoid adding a dep.
    // Secret Manager returns standard base64.
    let clean: String = s.chars().filter(|c| !c.is_whitespace()).collect();
    let table: [i8; 256] = build_table();
    let mut out = Vec::with_capacity(clean.len() * 3 / 4);
    let mut buf: u32 = 0;
    let mut bits: u32 = 0;
    for c in clean.bytes() {
        if c == b'=' {
            break;
        }
        let v = table[c as usize];
        if v < 0 {
            return Err(format!("bad base64 char: {}", c));
        }
        buf = (buf << 6) | v as u32;
        bits += 6;
        if bits >= 8 {
            bits -= 8;
            out.push(((buf >> bits) & 0xff) as u8);
        }
    }
    Ok(out)
}

fn build_table() -> [i8; 256] {
    let mut t = [-1i8; 256];
    let alphabet = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    for (i, c) in alphabet.iter().enumerate() {
        t[*c as usize] = i as i8;
    }
    t
}

#[async_trait]
impl ConfigSource for SecretManagerConfig {
    async fn kill_switch(&self) -> Result<KillSwitch, PortError> {
        Ok(KillSwitch::new(self.cached.read().await.kill))
    }
    async fn bounds(&self) -> Result<(f64, f64), PortError> {
        let p = self.cached.read().await;
        Ok((p.bounds_min, p.bounds_max))
    }
    async fn canary_ratio_bp(&self) -> Result<u16, PortError> {
        Ok(self.cached.read().await.canary_bp)
    }
}
