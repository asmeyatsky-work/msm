# Staging environment overrides.
# Synthetic data tolerates more null/zero outputs (see project_state memory).

env    = "staging"
region = "europe-west2"

# PRD §5 — relaxed for synthetic-data extrapolation.
anomaly_threshold   = 0.50
anomaly_window_secs = 300
anomaly_min_samples = 50

# Vertex `xgboost-cpu.1-7` on e2-standard-2 (staging) measures p50 ~700ms /
# p95 ~920ms for /v1/score; the 500ms timeout will trip frequently. Raised so
# load-test/demos don't tag every other call as a breaker false-positive.
model_timeout_ms = 1500
bq_timeout_ms    = 500

scoring_api_min_instances = 1
scoring_api_max_instances = 10
scoring_api_concurrency   = 80

# Threshold matches measured p95 + headroom (Phase 1.5 load profile 2026-04-28).
scoring_api_p95_threshold_ms = 1500

alert_notification_channels = ["projects/msm-rpc/notificationChannels/8278217269236288302"]
