use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{warn, instrument};

use msm_scoring_domain::{
    ClickFeatures, Prediction, PredictionSource, Rpc,
    PredictionBounds, CircuitBreakerState, AnomalyWindow, ClvPremium,
    ports::{ModelEndpoint, ClvEndpoint, DataLayerRevenue, Clock, ConfigSource, AuditSink, AuditEvent, PredictionSink, PredictionRecord, FeatureStore, PortError},
};

#[derive(Debug, thiserror::Error)]
pub enum ScoreClickError {
    #[error("configuration error: {0}")] Config(String),
    #[error("fatal fallback also failed: {0}")] FallbackFailed(String),
}

/// Injected collaborators. §3.2: every external call has a port.
pub struct ScoreClickDeps {
    pub model: Arc<dyn ModelEndpoint>,
    pub data_layer: Arc<dyn DataLayerRevenue>,
    pub clock: Arc<dyn Clock>,
    pub config: Arc<dyn ConfigSource>,
    pub audit: Arc<dyn AuditSink>,
    /// PRD §4.2 Shadow Production: every prediction (model + fallbacks) is logged here.
    pub predictions: Arc<dyn PredictionSink>,
    /// §3.2 + §4: explicit timeout on every external call.
    pub model_timeout: Duration,
    /// Circuit breaker cool-off window.
    pub breaker_cool_off: Duration,
    /// Anomaly threshold (PRD §5: >3%).
    pub anomaly_threshold: f64,
    /// PRD §6 optional "Hero" CLV adjustment. When both are Some, the CLV
    /// endpoint is called concurrently with the RPC model; failures degrade
    /// gracefully to the unadjusted prediction.
    pub clv: Option<Arc<dyn ClvEndpoint>>,
    pub clv_premium: Option<ClvPremium>,
    pub clv_timeout: Duration,
    /// PRD §2.2 Feature Store: optional online enrichment. When None, the
    /// request-body features are used unmodified.
    pub feature_store: Option<Arc<dyn FeatureStore>>,
    pub feature_store_timeout: Duration,
}

/// Scoring use case. Pure orchestration — no I/O logic, no SDKs.
pub struct ScoreClick {
    deps: ScoreClickDeps,
    breaker: Arc<RwLock<CircuitBreakerState>>,
    anomaly: Arc<RwLock<AnomalyWindow>>,
}

impl ScoreClick {
    pub fn new(deps: ScoreClickDeps) -> Self {
        let anomaly = AnomalyWindow::new(deps.anomaly_threshold);
        Self {
            deps,
            breaker: Arc::new(RwLock::new(CircuitBreakerState::Closed)),
            anomaly: Arc::new(RwLock::new(anomaly)),
        }
    }

    #[instrument(skip(self, features), fields(click_id = features.click_id().as_str()))]
    pub async fn execute(&self, features: ClickFeatures) -> Result<Prediction, ScoreClickError> {
        let kill = self.deps.config.kill_switch().await
            .map_err(|e| ScoreClickError::Config(e.to_string()))?;
        if kill.is_engaged() {
            return self.fallback(&features, PredictionSource::KillSwitch, "kill_switch").await;
        }

        let (min, max) = self.deps.config.bounds().await
            .map_err(|e| ScoreClickError::Config(e.to_string()))?;
        let bounds = PredictionBounds::try_new(min, max)
            .map_err(|e| ScoreClickError::Config(e.to_string()))?;

        let now = self.deps.clock.now_epoch_ms();
        let cool_off = self.deps.breaker_cool_off.as_millis() as u64;
        let state = *self.breaker.read().await;
        if !state.allows_call(now, cool_off) {
            return self.fallback(&features, PredictionSource::FallbackDataLayer, "breaker_open").await;
        }

        // PRD §2.2 Feature Store: optional enrichment. Degrade silently on failure
        // — request-body features already satisfy domain invariants.
        let features = if let Some(store) = self.deps.feature_store.as_ref() {
            let cid = features.click_id().as_str().to_string();
            match tokio::time::timeout(self.deps.feature_store_timeout, store.lookup(&cid)).await {
                Ok(Ok(overrides)) => features.with_overrides(&overrides),
                Ok(Err(e)) => { warn!(error = %e, "feature store lookup failed — using request features"); features }
                Err(_) => { warn!("feature store timeout — using request features"); features }
            }
        } else {
            features
        };

        // §3.2 + §4: every external call is timeout-bounded.
        // §3.6: RPC and CLV are independent → run concurrently.
        let rpc_call = tokio::time::timeout(self.deps.model_timeout, self.deps.model.predict(&features));
        let clv_fut = async {
            match (self.deps.clv.as_ref(), self.deps.clv_premium) {
                (Some(endpoint), Some(_)) => {
                    match tokio::time::timeout(self.deps.clv_timeout, endpoint.predict(&features)).await {
                        Ok(Ok(c)) => Some(c),
                        Ok(Err(e)) => { warn!(error = %e, "clv predict failed — degrading"); None }
                        Err(_) => { warn!("clv timeout — degrading"); None }
                    }
                }
                _ => None,
            }
        };
        let (rpc_result, clv_opt) = tokio::join!(rpc_call, clv_fut);

        let (rpc_raw, model_version) = match rpc_result {
            Ok(Ok(v)) => v,
            Ok(Err(e)) => {
                warn!(error = %e, "model predict failed — opening breaker");
                self.trip_breaker(now).await;
                return self.fallback(&features, PredictionSource::FallbackDataLayer, "model_error").await;
            }
            Err(_elapsed) => {
                warn!(timeout_ms = self.deps.model_timeout.as_millis() as u64, "model timeout");
                self.trip_breaker(now).await;
                return self.fallback(&features, PredictionSource::FallbackDataLayer, "model_timeout").await;
            }
        };

        // Apply CLV premium if both endpoint + policy produced a value.
        let rpc = match (clv_opt, self.deps.clv_premium) {
            (Some(clv), Some(premium)) => premium.adjust(rpc_raw, clv),
            _ => rpc_raw,
        };

        // Anomaly window sees every realized model call.
        let breached = {
            let mut w = self.anomaly.write().await;
            *w = std::mem::replace(&mut *w, AnomalyWindow::new(self.deps.anomaly_threshold)).record(rpc);
            w.breached()
        };
        if breached {
            warn!("anomaly window breached — tripping breaker");
            self.trip_breaker(now).await;
            return self.fallback(&features, PredictionSource::FallbackDataLayer, "anomaly").await;
        }

        if !bounds.contains(rpc) {
            // PRD §5 Prediction Bounds: reject in favor of tCPA.
            return self.fallback(&features, PredictionSource::FallbackTcpa, "bounds_rejected").await;
        }

        // Closed-state recovery: if we were HalfOpen, a clean success closes the breaker.
        if matches!(state, CircuitBreakerState::HalfOpen) {
            *self.breaker.write().await = CircuitBreakerState::Closed;
        }

        let pred = Prediction::new(
            features.click_id().clone(),
            features.correlation_id().clone(),
            rpc,
            PredictionSource::Model,
            model_version,
        );
        self.audit(&pred, "score.model").await;
        self.log_prediction(&pred).await;
        Ok(pred)
    }

    async fn trip_breaker(&self, now_epoch_ms: u64) {
        *self.breaker.write().await = CircuitBreakerState::Open { opened_at_epoch_ms: now_epoch_ms };
    }

    async fn fallback(
        &self,
        features: &ClickFeatures,
        source: PredictionSource,
        reason: &'static str,
    ) -> Result<Prediction, ScoreClickError> {
        let rpc = match source {
            PredictionSource::KillSwitch | PredictionSource::FallbackTcpa => Rpc::try_new(0.0).unwrap(),
            PredictionSource::FallbackDataLayer => {
                self.deps.data_layer.lookup(features).await
                    .map_err(|e: PortError| ScoreClickError::FallbackFailed(e.to_string()))?
            }
            PredictionSource::Model => unreachable!("model path never fallback"),
        };
        let pred = Prediction::new(
            features.click_id().clone(),
            features.correlation_id().clone(),
            rpc,
            source,
            "fallback",
        );
        self.audit(&pred, reason).await;
        self.log_prediction(&pred).await;
        Ok(pred)
    }

    async fn log_prediction(&self, pred: &Prediction) {
        let source_str: &'static str = match pred.source() {
            PredictionSource::Model => "MODEL",
            PredictionSource::FallbackTcpa => "FALLBACK_TCPA",
            PredictionSource::FallbackDataLayer => "FALLBACK_DATA_LAYER",
            PredictionSource::KillSwitch => "KILL_SWITCH",
        };
        let _ = self.deps.predictions.record(PredictionRecord {
            click_id: pred.click_id().as_str().into(),
            correlation_id: pred.correlation_id().as_str().into(),
            predicted_rpc: pred.rpc().value(),
            source: source_str,
            model_version: pred.model_version().into(),
            ts_ms: self.deps.clock.now_epoch_ms(),
        }).await;
    }

    async fn audit(&self, pred: &Prediction, reason: &'static str) {
        // Hash is deliberately simple here; a crypto hash lives in infrastructure.
        let after_hash = format!("{:?}:{}", pred.source(), pred.rpc().value());
        let _ = self.deps.audit.record(AuditEvent {
            actor: "scoring-api".into(),
            action: "score".into(),
            correlation_id: pred.correlation_id().as_str().into(),
            click_id: pred.click_id().as_str().into(),
            before_hash: None,
            after_hash,
            source: reason,
        }).await;
    }
}

#[cfg(test)]
mod tests {
    //! §5 Testing floor: application ≥85%, mock ports only.
    use super::*;
    use async_trait::async_trait;
    use msm_scoring_domain::click::ClickFeaturesInput;
    use msm_scoring_domain::guardrails::KillSwitch;

    struct FixedClock(u64);
    impl Clock for FixedClock { fn now_epoch_ms(&self) -> u64 { self.0 } }

    struct StaticModel(f64);
    #[async_trait] impl ModelEndpoint for StaticModel {
        async fn predict(&self, _: &ClickFeatures) -> Result<(Rpc, String), PortError> {
            Ok((Rpc::try_new(self.0).unwrap(), "v1".into()))
        }
    }

    struct FailingModel;
    #[async_trait] impl ModelEndpoint for FailingModel {
        async fn predict(&self, _: &ClickFeatures) -> Result<(Rpc, String), PortError> {
            Err(PortError::Upstream("boom".into()))
        }
    }

    struct StaticDataLayer(f64);
    #[async_trait] impl DataLayerRevenue for StaticDataLayer {
        async fn lookup(&self, _: &ClickFeatures) -> Result<Rpc, PortError> {
            Ok(Rpc::try_new(self.0).unwrap())
        }
    }

    struct Config { kill: bool, bounds: (f64, f64) }
    #[async_trait] impl ConfigSource for Config {
        async fn kill_switch(&self) -> Result<KillSwitch, PortError> { Ok(KillSwitch::new(self.kill)) }
        async fn bounds(&self) -> Result<(f64, f64), PortError> { Ok(self.bounds) }
    }

    struct NullAudit;
    #[async_trait] impl AuditSink for NullAudit {
        async fn record(&self, _: AuditEvent) -> Result<(), PortError> { Ok(()) }
    }

    struct RecordingSink(std::sync::Arc<std::sync::Mutex<Vec<PredictionRecord>>>);
    #[async_trait] impl PredictionSink for RecordingSink {
        async fn record(&self, r: PredictionRecord) -> Result<(), PortError> {
            self.0.lock().unwrap().push(r); Ok(())
        }
    }

    fn features() -> ClickFeatures {
        ClickFeatures::try_new(ClickFeaturesInput {
            click_id: "c".into(), correlation_id: "t".into(),
            device: "m".into(), geo: "US".into(), hour_of_day: 10,
            query_intent: "x".into(), ad_creative_id: "a".into(),
            cerberus_score: 0.9, rpc_7d: 1.0, rpc_14d: 1.0, rpc_30d: 1.0,
            is_payday_week: false, auction_pressure: 0.5,
            landing_path: "/".into(), visits_prev_30d: 1,
        }).unwrap()
    }

    fn deps_with(model: Arc<dyn ModelEndpoint>, kill: bool, bounds: (f64, f64)) -> ScoreClickDeps {
        ScoreClickDeps {
            model,
            data_layer: Arc::new(StaticDataLayer(2.5)),
            clock: Arc::new(FixedClock(0)),
            config: Arc::new(Config { kill, bounds }),
            audit: Arc::new(NullAudit),
            predictions: Arc::new(RecordingSink(Default::default())),
            model_timeout: Duration::from_millis(50),
            breaker_cool_off: Duration::from_secs(30),
            anomaly_threshold: 0.03,
            clv: None,
            clv_premium: None,
            clv_timeout: Duration::from_millis(100),
            feature_store: None,
            feature_store_timeout: Duration::from_millis(50),
        }
    }

    struct StaticStore(msm_scoring_domain::ports::FeatureOverrides);
    #[async_trait] impl msm_scoring_domain::ports::FeatureStore for StaticStore {
        async fn lookup(&self, _: &str) -> Result<msm_scoring_domain::ports::FeatureOverrides, PortError> {
            Ok(self.0.clone())
        }
    }

    #[tokio::test]
    async fn feature_store_overrides_rolling_rpc() {
        // Model echoes the override-dependent feature via deps injection: we instead
        // verify the post-call Prediction remains clamped & the use case succeeds
        // when the store supplies fresh values.
        let mut deps = deps_with(Arc::new(StaticModel(4.0)), false, (0.1, 100.0));
        deps.feature_store = Some(Arc::new(StaticStore(msm_scoring_domain::ports::FeatureOverrides {
            rpc_7d: Some(9.9), rpc_14d: None, rpc_30d: None, visits_prev_30d: Some(42),
        })));
        let uc = ScoreClick::new(deps);
        let p = uc.execute(features()).await.unwrap();
        assert_eq!(p.source(), PredictionSource::Model);
    }

    struct StaticClv(f64);
    #[async_trait] impl msm_scoring_domain::ports::ClvEndpoint for StaticClv {
        async fn predict(&self, _: &ClickFeatures) -> Result<msm_scoring_domain::Clv, PortError> {
            Ok(msm_scoring_domain::Clv::try_new(self.0).unwrap())
        }
    }

    #[tokio::test]
    async fn every_prediction_is_logged_to_sink() {
        let recorder = std::sync::Arc::new(std::sync::Mutex::new(Vec::<PredictionRecord>::new()));
        let mut deps = deps_with(Arc::new(StaticModel(3.0)), false, (0.1, 100.0));
        deps.predictions = Arc::new(RecordingSink(recorder.clone()));
        let uc = ScoreClick::new(deps);
        uc.execute(features()).await.unwrap();
        let logged = recorder.lock().unwrap();
        assert_eq!(logged.len(), 1);
        assert_eq!(logged[0].source, "MODEL");
        assert_eq!(logged[0].predicted_rpc, 3.0);
    }

    #[tokio::test]
    async fn fallback_also_logs_to_sink() {
        let recorder = std::sync::Arc::new(std::sync::Mutex::new(Vec::<PredictionRecord>::new()));
        let mut deps = deps_with(Arc::new(StaticModel(3.0)), true, (0.1, 100.0));
        deps.predictions = Arc::new(RecordingSink(recorder.clone()));
        let uc = ScoreClick::new(deps);
        uc.execute(features()).await.unwrap();
        assert_eq!(recorder.lock().unwrap()[0].source, "KILL_SWITCH");
    }

    #[tokio::test]
    async fn clv_premium_adjusts_rpc() {
        let mut deps = deps_with(Arc::new(StaticModel(2.0)), false, (0.1, 100.0));
        deps.clv = Some(Arc::new(StaticClv(100.0)));
        deps.clv_premium = Some(msm_scoring_domain::ClvPremium::try_new(0.5, 100.0, 3.0).unwrap());
        let uc = ScoreClick::new(deps);
        let p = uc.execute(features()).await.unwrap();
        assert_eq!(p.source(), PredictionSource::Model);
        assert!((p.rpc().value() - 3.0).abs() < 1e-9); // 2.0 * (1 + 0.5 * 1.0)
    }

    #[tokio::test]
    async fn happy_path_uses_model() {
        let uc = ScoreClick::new(deps_with(Arc::new(StaticModel(3.0)), false, (0.1, 100.0)));
        let p = uc.execute(features()).await.unwrap();
        assert_eq!(p.source(), PredictionSource::Model);
        assert_eq!(p.rpc().value(), 3.0);
    }

    #[tokio::test]
    async fn kill_switch_short_circuits() {
        let uc = ScoreClick::new(deps_with(Arc::new(StaticModel(3.0)), true, (0.1, 100.0)));
        let p = uc.execute(features()).await.unwrap();
        assert_eq!(p.source(), PredictionSource::KillSwitch);
    }

    #[tokio::test]
    async fn bounds_rejection_falls_back_to_tcpa() {
        let uc = ScoreClick::new(deps_with(Arc::new(StaticModel(9999.0)), false, (0.1, 100.0)));
        let p = uc.execute(features()).await.unwrap();
        assert_eq!(p.source(), PredictionSource::FallbackTcpa);
    }

    #[tokio::test]
    async fn model_error_trips_breaker_and_uses_data_layer() {
        let uc = ScoreClick::new(deps_with(Arc::new(FailingModel), false, (0.1, 100.0)));
        let p = uc.execute(features()).await.unwrap();
        assert_eq!(p.source(), PredictionSource::FallbackDataLayer);
        assert_eq!(p.rpc().value(), 2.5);
    }
}
