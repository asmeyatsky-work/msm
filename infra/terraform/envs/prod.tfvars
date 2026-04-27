# Prod environment overrides.
# Resize scoring_api_{min,max}_instances and concurrency from the Phase 1.5
# load profile (ops/perf/) before flipping vars.DEPLOY_PROD=true.

env    = "prod"
region = "europe-west2"

# PRD §5 prod values — strict.
anomaly_threshold   = 0.03
anomaly_window_secs = 300
anomaly_min_samples = 50

model_timeout_ms = 500
bq_timeout_ms    = 500

# Two replicas minimum for redundancy. Bump from load profile.
scoring_api_min_instances = 2
scoring_api_max_instances = 50
scoring_api_concurrency   = 80
