# Client-isolated Credit Cards environment (PRD V2 §6.1).
#
# Sized identically to staging: stays inside the Searce GCP project as a
# namespaced env (env="client-cc" suffixes every resource). No prod-grade
# scale-up here; once real client volume is known the load-profile drives
# the actual sizing (PRD V2 §5 Throughput, OQ-3).

env    = "client-cc"
region = "europe-west2"

# PRD V2 §5: production-grade strictness, not the synthetic-data relaxation
# used in staging. The 0.03 default in variables_runtime.tf is correct here.
anomaly_threshold   = 0.03
anomaly_window_secs = 300
anomaly_min_samples = 50

# Hold same timeouts as staging until first real load profile (OQ-3).
model_timeout_ms = 1500
bq_timeout_ms    = 500

scoring_api_min_instances = 1
scoring_api_max_instances = 10
scoring_api_concurrency   = 80

# Warmth on the executive surfaces so the client demo never cold-starts.
# Drop both to 0 after handover if cost matters.
reconciliation_min_instances = 1
dashboard_min_instances      = 1

# PRD V2 §4.5: Credit Cards reconciliation window is 90 days. This matches
# the default in variables_runtime.tf but pinning it explicitly here is
# what the PRD calls out as the env-bound contract.
reconciliation_window_days = 90

# Re-baseline once real client traffic is observed.
scoring_api_p95_threshold_ms = 1500

# Wire to the client's notification channel once provided (OQ-2).
alert_notification_channels = []
