//! # Scoring Presentation (HTTP)
//!
//! Layer: presentation. Wires adapters into the `ScoreClick` use case.
//! §4: validates all external input against a schema (serde + domain constructors).

use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;
use std::time::Instant;

use msm_scoring_application::{ExplainClick, ScoreClick, ScoreClickDeps};
use msm_scoring_domain::click::{ClickFeatures, ClickFeaturesInput};
use msm_scoring_domain::ports::ConfigSource;
use msm_scoring_infrastructure::{
    BigQueryDataLayer, PubSubAudit, PubSubPredictions, RuntimeConfig, SecretManagerConfig,
    SystemClock, VertexEndpoint, VertexExplain,
};

#[derive(Clone)]
struct AppState {
    use_case: Arc<ScoreClick>,
    explain: Arc<ExplainClick>,
}

#[derive(Deserialize)]
struct ScoreRequest {
    click_id: String,
    correlation_id: String,
    device: String,
    geo: String,
    hour_of_day: i32,
    query_intent: String,
    ad_creative_id: String,
    cerberus_score: f64,
    rpc_7d: f64,
    rpc_14d: f64,
    rpc_30d: f64,
    is_payday_week: bool,
    auction_pressure: f64,
    landing_path: String,
    visits_prev_30d: u32,
}

#[derive(Serialize)]
struct ScoreResponse {
    click_id: String,
    predicted_rpc: f64,
    source: String,
    model_version: String,
    correlation_id: String,
}

async fn score_handler(
    State(state): State<AppState>,
    Json(req): Json<ScoreRequest>,
) -> Result<Json<ScoreResponse>, (StatusCode, String)> {
    // §4: Reject-by-default via domain constructor invariants.
    let features = ClickFeatures::try_new(ClickFeaturesInput {
        click_id: req.click_id,
        correlation_id: req.correlation_id,
        device: req.device,
        geo: req.geo,
        hour_of_day: req.hour_of_day,
        query_intent: req.query_intent,
        ad_creative_id: req.ad_creative_id,
        cerberus_score: req.cerberus_score,
        rpc_7d: req.rpc_7d,
        rpc_14d: req.rpc_14d,
        rpc_30d: req.rpc_30d,
        is_payday_week: req.is_payday_week,
        auction_pressure: req.auction_pressure,
        landing_path: req.landing_path,
        visits_prev_30d: req.visits_prev_30d,
    })
    .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;

    let pred = state
        .use_case
        .execute(features)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    Ok(Json(ScoreResponse {
        click_id: pred.click_id().as_str().into(),
        predicted_rpc: pred.rpc().value(),
        source: format!("{:?}", pred.source()),
        model_version: pred.model_version().into(),
        correlation_id: pred.correlation_id().as_str().into(),
    }))
}

#[derive(Serialize)]
struct ExplainResponse {
    click_id: String,
    base_value: f64,
    contributions: Vec<(String, f64)>,
}

async fn explain_handler(
    State(state): State<AppState>,
    Json(req): Json<ScoreRequest>,
) -> Result<Json<ExplainResponse>, (StatusCode, String)> {
    let features = ClickFeatures::try_new(ClickFeaturesInput {
        click_id: req.click_id.clone(),
        correlation_id: req.correlation_id,
        device: req.device,
        geo: req.geo,
        hour_of_day: req.hour_of_day,
        query_intent: req.query_intent,
        ad_creative_id: req.ad_creative_id,
        cerberus_score: req.cerberus_score,
        rpc_7d: req.rpc_7d,
        rpc_14d: req.rpc_14d,
        rpc_30d: req.rpc_30d,
        is_payday_week: req.is_payday_week,
        auction_pressure: req.auction_pressure,
        landing_path: req.landing_path,
        visits_prev_30d: req.visits_prev_30d,
    })
    .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;

    let a = state
        .explain
        .execute(features)
        .await
        .map_err(|e| (StatusCode::BAD_GATEWAY, e.to_string()))?;
    Ok(Json(ExplainResponse {
        click_id: req.click_id,
        base_value: a.base_value,
        contributions: a.contributions,
    }))
}

async fn healthz() -> &'static str {
    "ok"
}

async fn metrics_handler(
    State(handle): State<metrics_exporter_prometheus::PrometheusHandle>,
) -> String {
    handle.render()
}

/// RED middleware (§6): Rate / Errors / Duration per endpoint.
async fn red_middleware(req: Request, next: Next) -> Response {
    let path = req.uri().path().to_string();
    let method = req.method().to_string();
    let start = Instant::now();
    let resp = next.run(req).await;
    let status = resp.status().as_u16();
    let labels = [
        ("path", path),
        ("method", method),
        ("status", status.to_string()),
    ];
    metrics::counter!("http_requests_total", &labels).increment(1);
    metrics::histogram!("http_request_duration_seconds", &labels)
        .record(start.elapsed().as_secs_f64());
    if status >= 500 {
        metrics::counter!("http_request_errors_total", &labels).increment(1);
    }
    resp
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    init_telemetry()?;

    // §4: never read secrets from env-default; a non-present endpoint URL means
    // the service refuses to start.
    let vertex_url = std::env::var("VERTEX_ENDPOINT_URL")
        .map_err(|_| "VERTEX_ENDPOINT_URL must be provided via Secret Manager/Workload Identity")?;
    let model_version = std::env::var("MODEL_VERSION").unwrap_or_else(|_| "unknown".into());
    let bounds_min: f64 = std::env::var("RPC_MIN")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(0.01);
    let bounds_max: f64 = std::env::var("RPC_MAX")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(500.0);
    let kill: bool = std::env::var("KILL_SWITCH")
        .ok()
        .map(|v| v == "true")
        .unwrap_or(false);

    // Prefer Secret-Manager-backed config so the breaker-automation function
    // can flip the kill switch by writing a new secret version (PRD §5,
    // no redeploy). Fall back to env-backed RuntimeConfig for local dev.
    let config: Arc<dyn ConfigSource> = match (
        std::env::var("GCP_PROJECT").ok(),
        std::env::var("RUNTIME_CONFIG_SECRET").ok(),
    ) {
        (Some(project), Some(secret_id)) => Arc::new(
            SecretManagerConfig::new(
                project,
                secret_id,
                Duration::from_secs(15),
                Duration::from_millis(500),
            )
            .await
            .map_err(|e| format!("runtime config init: {e}"))?,
        ),
        _ => Arc::new(RuntimeConfig::new(kill, bounds_min, bounds_max)),
    };

    // PRD §2.2 bundgets 100ms total. Cloud Run → Vertex AI round-trip in the
    // same region is typically 50-300ms (warm). Make configurable so the
    // deploy can tune vs. SLO without a code change.
    let model_timeout_ms: u64 = std::env::var("MODEL_TIMEOUT_MS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(500);
    let bq_timeout_ms: u64 = std::env::var("BQ_TIMEOUT_MS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(500);

    let deps = ScoreClickDeps {
        model: Arc::new(VertexEndpoint::new(
            vertex_url,
            model_version,
            Duration::from_millis(model_timeout_ms),
        )),
        data_layer: Arc::new(BigQueryDataLayer::new(
            std::env::var("GCP_PROJECT").map_err(|_| "GCP_PROJECT required")?,
            std::env::var("BQ_DATASET").map_err(|_| "BQ_DATASET required")?,
            std::env::var("BQ_LEDGER_TABLE").unwrap_or_else(|_| "sales_ledger".into()),
            Duration::from_millis(bq_timeout_ms),
        )),
        clock: Arc::new(SystemClock),
        config,
        audit: Arc::new(PubSubAudit::new("scoring-audit".into())),
        predictions: Arc::new(PubSubPredictions::new(
            std::env::var("GCP_PROJECT").map_err(|_| "GCP_PROJECT required")?,
            std::env::var("PREDICTIONS_TOPIC").unwrap_or_else(|_| "rpc-predictions".into()),
            Duration::from_millis(200),
        )),
        model_timeout: Duration::from_millis(model_timeout_ms),
        breaker_cool_off: Duration::from_secs(30),
        anomaly_threshold: std::env::var("ANOMALY_THRESHOLD")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(0.03), // PRD §5: >3% null/zero default
        // PRD §6 Hero feature — enable when both endpoint + policy are set.
        clv: std::env::var("CLV_ENDPOINT_URL").ok().map(|url| {
            let arc: Arc<dyn msm_scoring_domain::ports::ClvEndpoint> = Arc::new(
                msm_scoring_infrastructure::VertexClvEndpoint::new(url, Duration::from_millis(80)),
            );
            arc
        }),
        clv_premium: match (
            std::env::var("CLV_ALPHA").ok().and_then(|v| v.parse().ok()),
            std::env::var("CLV_REFERENCE")
                .ok()
                .and_then(|v| v.parse().ok()),
            std::env::var("CLV_CAP").ok().and_then(|v| v.parse().ok()),
        ) {
            (Some(a), Some(r), Some(c)) => msm_scoring_domain::ClvPremium::try_new(a, r, c).ok(),
            _ => None,
        },
        clv_timeout: Duration::from_millis(80),
        feature_store: match (
            std::env::var("GCP_REGION").ok(),
            std::env::var("FEATURE_VIEW").ok(),
        ) {
            (Some(region), Some(fv)) => {
                let arc: Arc<dyn msm_scoring_domain::ports::FeatureStore> =
                    Arc::new(msm_scoring_infrastructure::VertexFeatureStore::new(
                        region,
                        fv,
                        Duration::from_millis(40),
                    ));
                Some(arc)
            }
            _ => None,
        },
        feature_store_timeout: Duration::from_millis(40),
    };
    let use_case = Arc::new(ScoreClick::new(deps));

    let explain_url =
        std::env::var("VERTEX_EXPLAIN_URL").map_err(|_| "VERTEX_EXPLAIN_URL must be provided")?;
    let explain = Arc::new(ExplainClick::new(
        Arc::new(VertexExplain::new(explain_url, Duration::from_millis(1500))),
        Duration::from_millis(1500), // explain is slow; off hot path
    ));

    // Prometheus registry for /metrics (scraped by Cloud Monitoring Managed Service).
    let prom = metrics_exporter_prometheus::PrometheusBuilder::new()
        .install_recorder()
        .map_err(|e| format!("prometheus recorder: {e}"))?;

    let app_state = AppState { use_case, explain };
    let api = Router::new()
        .route("/health", get(healthz))
        .route("/v1/score", post(score_handler))
        .route("/v1/explain", post(explain_handler))
        .with_state(app_state)
        .layer(middleware::from_fn(red_middleware));

    let metrics_router = Router::new()
        .route("/metrics", get(metrics_handler))
        .with_state(prom);

    let app = api.merge(metrics_router);

    let addr = std::env::var("LISTEN_ADDR").unwrap_or_else(|_| "0.0.0.0:8080".into());
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    tracing::info!(%addr, "scoring-api listening");
    axum::serve(listener, app).await?;
    Ok(())
}

/// §6: structured JSON logs + OTLP traces. Correlation id flows via span fields.
fn init_telemetry() -> Result<(), Box<dyn std::error::Error>> {
    use tracing_subscriber::prelude::*;
    use tracing_subscriber::EnvFilter;

    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    let json_layer = tracing_subscriber::fmt::layer().json().with_target(true);

    let otlp_endpoint = std::env::var("OTEL_EXPORTER_OTLP_ENDPOINT").ok();
    let registry = tracing_subscriber::registry().with(filter).with(json_layer);

    if let Some(endpoint) = otlp_endpoint {
        use opentelemetry::trace::TracerProvider as _;
        use opentelemetry_otlp::WithExportConfig;
        let exporter = opentelemetry_otlp::SpanExporter::builder()
            .with_tonic()
            .with_endpoint(endpoint)
            .build()?;
        let provider = opentelemetry_sdk::trace::TracerProvider::builder()
            .with_batch_exporter(exporter, opentelemetry_sdk::runtime::Tokio)
            .build();
        let tracer = provider.tracer("scoring-api");
        opentelemetry::global::set_tracer_provider(provider);
        let otel_layer = tracing_opentelemetry::layer().with_tracer(tracer);
        registry.with(otel_layer).init();
    } else {
        registry.init();
    }
    Ok(())
}
