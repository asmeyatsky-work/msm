//! End-to-end integration test: wires real HTTP adapters into ScoreClick and
//! drives timeout + success + bounds-rejection through wiremock (§5).

use serde_json::json;
use std::sync::Arc;
use std::time::Duration;
use wiremock::matchers::{method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

use async_trait::async_trait;
use msm_scoring_application::{ScoreClick, ScoreClickDeps};
use msm_scoring_domain::{
    click::ClickFeaturesInput,
    ports::{
        AuditEvent, AuditSink, Clock, DataLayerRevenue, PortError, PredictionRecord, PredictionSink,
    },
    ClickFeatures, PredictionSource, Rpc,
};
use msm_scoring_infrastructure::{RuntimeConfig, VertexEndpoint};

struct NullAudit;
#[async_trait]
impl AuditSink for NullAudit {
    async fn record(&self, _: AuditEvent) -> Result<(), PortError> {
        Ok(())
    }
}

struct NullPredictions;
#[async_trait]
impl PredictionSink for NullPredictions {
    async fn record(&self, _: PredictionRecord) -> Result<(), PortError> {
        Ok(())
    }
}

struct StaticDataLayer(f64);
#[async_trait]
impl DataLayerRevenue for StaticDataLayer {
    async fn lookup(&self, _: &ClickFeatures) -> Result<Rpc, PortError> {
        Ok(Rpc::try_new(self.0).unwrap())
    }
}

struct FixedClock(u64);
impl Clock for FixedClock {
    fn now_epoch_ms(&self) -> u64 {
        self.0
    }
}

fn features() -> ClickFeatures {
    ClickFeatures::try_new(ClickFeaturesInput {
        click_id: "c-int".into(),
        correlation_id: "t-int".into(),
        device: "m".into(),
        geo: "US".into(),
        hour_of_day: 10,
        query_intent: "x".into(),
        ad_creative_id: "a".into(),
        cerberus_score: 0.9,
        rpc_7d: 1.0,
        rpc_14d: 1.0,
        rpc_30d: 1.0,
        is_payday_week: false,
        auction_pressure: 0.5,
        landing_path: "/".into(),
        visits_prev_30d: 1,
    })
    .unwrap()
}

async fn stub_metadata_token(server: &MockServer) {
    Mock::given(method("GET"))
        .and(path("/token"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "access_token": "fake", "expires_in": 3600
        })))
        .mount(server)
        .await;
}

fn build_uc(vertex_url: String) -> ScoreClick {
    let deps = ScoreClickDeps {
        model: Arc::new(VertexEndpoint::new(
            vertex_url,
            "v-int".into(),
            Duration::from_millis(200),
        )),
        data_layer: Arc::new(StaticDataLayer(2.5)),
        clock: Arc::new(FixedClock(0)),
        config: Arc::new(RuntimeConfig::new(false, 0.1, 100.0)),
        audit: Arc::new(NullAudit),
        predictions: Arc::new(NullPredictions),
        model_timeout: Duration::from_millis(200),
        breaker_cool_off: Duration::from_secs(30),
        anomaly_threshold: 0.03,
        clv: None,
        clv_premium: None,
        clv_timeout: Duration::from_millis(200),
        feature_store: None,
        feature_store_timeout: Duration::from_millis(50),
    };
    ScoreClick::new(deps)
}

#[tokio::test]
async fn vertex_happy_path_returns_model_source() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_metadata_token(&server).await;

    Mock::given(method("POST"))
        .and(path("/predict"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({"predictions": [4.2]})))
        .mount(&server)
        .await;

    let uc = build_uc(format!("{}/predict", server.uri()));
    let p = uc.execute(features()).await.unwrap();
    assert_eq!(p.source(), PredictionSource::Model);
    assert!((p.rpc().value() - 4.2).abs() < 1e-9);
}

#[tokio::test]
async fn vertex_timeout_trips_breaker_and_falls_back() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_metadata_token(&server).await;

    Mock::given(method("POST"))
        .and(path("/predict"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_json(json!({"predictions": [1.0]}))
                .set_delay(Duration::from_millis(500)),
        ) // exceeds 200ms timeout
        .mount(&server)
        .await;

    let uc = build_uc(format!("{}/predict", server.uri()));
    let p = uc.execute(features()).await.unwrap();
    assert_eq!(p.source(), PredictionSource::FallbackDataLayer);
    assert_eq!(p.rpc().value(), 2.5);
}

#[tokio::test]
async fn vertex_out_of_bounds_prediction_falls_back_to_tcpa() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_metadata_token(&server).await;

    Mock::given(method("POST"))
        .and(path("/predict"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({"predictions": [9999.0]})))
        .mount(&server)
        .await;

    let uc = build_uc(format!("{}/predict", server.uri()));
    let p = uc.execute(features()).await.unwrap();
    assert_eq!(p.source(), PredictionSource::FallbackTcpa);
}
