# Staging environment overrides.
# Synthetic data tolerates more null/zero outputs (see project_state memory).

env    = "staging"
region = "europe-west2"

# PRD §5 — relaxed for synthetic-data extrapolation.
anomaly_threshold   = 0.50
anomaly_window_secs = 300
anomaly_min_samples = 50

model_timeout_ms = 500
bq_timeout_ms    = 500

scoring_api_min_instances = 1
scoring_api_max_instances = 10
scoring_api_concurrency   = 80
