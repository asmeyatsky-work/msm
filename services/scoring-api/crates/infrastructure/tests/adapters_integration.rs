//! Integration tests for each infrastructure adapter driven through real HTTP
//! via wiremock. Protocol regressions (wrong URL shape, wrong JSON path, bad
//! status handling) fail here, not in prod.

use serde_json::json;
use std::time::Duration;
use wiremock::matchers::{method, path, path_regex};
use wiremock::{Mock, MockServer, ResponseTemplate};

use msm_scoring_domain::{
    click::ClickFeaturesInput,
    ports::{
        ClvEndpoint, ConfigSource, DataLayerRevenue, ExplainEndpoint, PortError, PredictionRecord,
        PredictionSink,
    },
    ClickFeatures,
};
use msm_scoring_infrastructure::{
    BigQueryDataLayer, PubSubPredictions, SecretManagerConfig, VertexClvEndpoint, VertexExplain,
};

fn features() -> ClickFeatures {
    ClickFeatures::try_new(ClickFeaturesInput {
        click_id: "c-adapt".into(),
        correlation_id: "t".into(),
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

async fn stub_token(server: &MockServer) {
    Mock::given(method("GET"))
        .and(path("/token"))
        .respond_with(
            ResponseTemplate::new(200)
                .set_body_json(json!({"access_token": "fake", "expires_in": 3600})),
        )
        .mount(server)
        .await;
}

// ---------- VertexExplain ----------

#[tokio::test]
async fn vertex_explain_parses_attributions() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_token(&server).await;
    Mock::given(method("POST"))
        .and(path("/explain"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "explanations": [{"attributions": [{
                "baselineOutputValue": 1.5,
                "featureAttributions": {"rpc_7d": 0.3, "cerberus_score": -0.1}
            }]}]
        })))
        .mount(&server)
        .await;
    let ep = VertexExplain::new(format!("{}/explain", server.uri()), Duration::from_secs(2));
    let a = ep.explain(&features()).await.unwrap();
    assert!((a.base_value - 1.5).abs() < 1e-9);
    assert_eq!(a.top_features(1)[0].0, "rpc_7d");
}

#[tokio::test]
async fn vertex_explain_errors_on_non_2xx() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_token(&server).await;
    Mock::given(method("POST"))
        .and(path("/explain"))
        .respond_with(ResponseTemplate::new(500))
        .mount(&server)
        .await;
    let ep = VertexExplain::new(format!("{}/explain", server.uri()), Duration::from_secs(2));
    assert!(matches!(
        ep.explain(&features()).await,
        Err(PortError::Upstream(_))
    ));
}

// ---------- VertexClvEndpoint ----------

#[tokio::test]
async fn vertex_clv_parses_prediction() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_token(&server).await;
    Mock::given(method("POST"))
        .and(path("/clv"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({"predictions": [250.0]})))
        .mount(&server)
        .await;
    let ep = VertexClvEndpoint::new(format!("{}/clv", server.uri()), Duration::from_secs(2));
    assert!((ep.predict(&features()).await.unwrap().value() - 250.0).abs() < 1e-9);
}

#[tokio::test]
async fn vertex_clv_rejects_missing_prediction_field() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_token(&server).await;
    Mock::given(method("POST"))
        .and(path("/clv"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({})))
        .mount(&server)
        .await;
    let ep = VertexClvEndpoint::new(format!("{}/clv", server.uri()), Duration::from_secs(2));
    assert!(matches!(
        ep.predict(&features()).await,
        Err(PortError::Upstream(_))
    ));
}

// ---------- BigQueryDataLayer (via api_root DI) ----------

#[tokio::test]
async fn bigquery_data_layer_sums_jobs_query_rows() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_token(&server).await;
    Mock::given(method("POST"))
        .and(path_regex(r".*/projects/proj/queries$"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "rows": [{"f": [{"v": "12.50"}]}]
        })))
        .mount(&server)
        .await;
    let bq = BigQueryDataLayer::with_api_root(
        server.uri(),
        "proj".into(),
        "ds".into(),
        "tbl".into(),
        Duration::from_secs(2),
    );
    assert!((bq.lookup(&features()).await.unwrap().value() - 12.50).abs() < 1e-9);
}

#[tokio::test]
async fn bigquery_data_layer_defaults_to_zero_for_empty_rows() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_token(&server).await;
    Mock::given(method("POST"))
        .and(path_regex(r".*/projects/proj/queries$"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({"rows": []})))
        .mount(&server)
        .await;
    let bq = BigQueryDataLayer::with_api_root(
        server.uri(),
        "proj".into(),
        "ds".into(),
        "tbl".into(),
        Duration::from_secs(2),
    );
    assert_eq!(bq.lookup(&features()).await.unwrap().value(), 0.0);
}

// ---------- PubSubPredictions (via api_root DI) ----------

#[tokio::test]
async fn pubsub_predictions_publishes_message_payload() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_token(&server).await;
    Mock::given(method("POST"))
        .and(path_regex(r".*/topics/t-int:publish$"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({"messageIds": ["1"]})))
        .mount(&server)
        .await;
    let sink = PubSubPredictions::with_api_root(
        server.uri(),
        "proj".into(),
        "t-int".into(),
        Duration::from_secs(2),
    );
    sink.record(PredictionRecord {
        click_id: "c-1".into(),
        correlation_id: "t".into(),
        predicted_rpc: 2.5,
        source: "MODEL",
        model_version: "v1".into(),
        ts_ms: 1,
    })
    .await
    .unwrap();
}

#[tokio::test]
async fn pubsub_predictions_surfaces_non_2xx() {
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_token(&server).await;
    Mock::given(method("POST"))
        .and(path_regex(r".*:publish$"))
        .respond_with(ResponseTemplate::new(503))
        .mount(&server)
        .await;
    let sink = PubSubPredictions::with_api_root(
        server.uri(),
        "proj".into(),
        "t".into(),
        Duration::from_secs(2),
    );
    assert!(sink
        .record(PredictionRecord {
            click_id: "c".into(),
            correlation_id: "t".into(),
            predicted_rpc: 1.0,
            source: "MODEL",
            model_version: "v".into(),
            ts_ms: 1,
        })
        .await
        .is_err());
}

// ---------- SecretManagerConfig (via SECRETMANAGER_API_ROOT env) ----------

#[tokio::test]
async fn secret_manager_config_initial_fetch_returns_typed_values() {
    use base64::Engine;
    let server = MockServer::start().await;
    std::env::set_var("GCP_METADATA_TOKEN_URL", format!("{}/token", server.uri()));
    stub_token(&server).await;
    let payload = r#"{"kill": true, "bounds_min": 0.5, "bounds_max": 42.0, "canary_bp": 2500}"#;
    let b64 = base64::engine::general_purpose::STANDARD.encode(payload);
    Mock::given(method("GET"))
        .and(path_regex(r".*/secrets/.*:access$"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "name": "projects/p/secrets/s/versions/1",
            "payload": {"data": b64}
        })))
        .mount(&server)
        .await;

    let cfg = SecretManagerConfig::with_api_root(
        server.uri(),
        "proj".into(),
        "rt".into(),
        Duration::from_secs(60),
        Duration::from_secs(2),
    )
    .await
    .unwrap();

    assert!(cfg.kill_switch().await.unwrap().is_engaged());
    let (lo, hi) = cfg.bounds().await.unwrap();
    assert!((lo - 0.5).abs() < 1e-9 && (hi - 42.0).abs() < 1e-9);
    assert_eq!(cfg.canary_ratio_bp().await.unwrap(), 2500);
}
