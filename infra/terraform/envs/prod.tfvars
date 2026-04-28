# Prod environment overrides.
#
# Phase 1.5 load profile (2026-04-28, ops/perf/) on the *staging* stack
# (Vertex `xgboost-cpu.1-7` on `e2-standard-2`, single replica):
#   /v1/score   — p50 736ms, p95 920ms,  p99 1300ms, 7.4% 5xx during scale-out
#   /v1/explain — p50 1339ms, p95 1820ms, p99 2105ms (sampled-shapley path=10)
# `model_timeout_ms = 500` will time out against this Vertex config — prod
# must redeploy the model on a larger machine (target n1-standard-4 or
# n2-standard-4) AND keep `min_replica_count >= 2` to absorb autoscale gap.
# Update `ops/deploy_real_model.py:125` before bootstrapping prod.

env    = "prod"
region = "europe-west2"

# PRD §5 prod values — strict.
anomaly_threshold   = 0.03
anomaly_window_secs = 300
anomaly_min_samples = 50

# Tightened from the staging-load-test p50 (~700ms) once prod model is on a
# bigger Vertex machine; if you keep e2-standard-2, raise this to 1500.
model_timeout_ms = 500
bq_timeout_ms    = 500

# Two replicas minimum for redundancy + autoscale headroom (staging saw 7.4%
# 5xx during single-replica scale-out under c=10). Concurrency lowered from 80
# because each request blocks ~700ms on Vertex; 40 keeps queue depth sane.
scoring_api_min_instances = 2
scoring_api_max_instances = 50
scoring_api_concurrency   = 40

# Score-path p95 alert. With prod on a bigger Vertex machine targeting
# p95 ~400ms, this is generous; tighten after first week of traffic.
scoring_api_p95_threshold_ms = 800
