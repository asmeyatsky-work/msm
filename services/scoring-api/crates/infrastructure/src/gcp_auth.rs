//! GCP auth — Workload Identity / metadata-server token fetcher (§4).
//! No business logic; just a thin adapter with a refresh cache.

use std::time::{Duration, Instant};
use tokio::sync::RwLock;

#[derive(Clone, Debug)]
struct CachedToken {
    value: String,
    expires_at: Instant,
}

pub struct MetadataTokenSource {
    http: reqwest::Client,
    cache: RwLock<Option<CachedToken>>,
    metadata_url: String,
}

impl MetadataTokenSource {
    pub fn new(timeout: Duration) -> Self {
        let http = reqwest::Client::builder()
            .timeout(timeout)
            .build()
            .expect("client");
        Self {
            http,
            cache: RwLock::new(None),
            metadata_url: std::env::var("GCP_METADATA_TOKEN_URL").unwrap_or_else(|_|
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token".into()),
        }
    }

    pub async fn token(&self) -> Result<String, String> {
        if let Some(c) = self.cache.read().await.clone() {
            if c.expires_at > Instant::now() + Duration::from_secs(30) {
                return Ok(c.value);
            }
        }
        let resp = self
            .http
            .get(&self.metadata_url)
            .header("Metadata-Flavor", "Google")
            .send()
            .await
            .map_err(|e| e.to_string())?;
        if !resp.status().is_success() {
            return Err(format!("metadata status {}", resp.status()));
        }
        #[derive(serde::Deserialize)]
        struct T {
            access_token: String,
            expires_in: u64,
        }
        let t: T = resp.json().await.map_err(|e| e.to_string())?;
        let cached = CachedToken {
            value: t.access_token.clone(),
            expires_at: Instant::now() + Duration::from_secs(t.expires_in),
        };
        *self.cache.write().await = Some(cached);
        Ok(t.access_token)
    }
}
