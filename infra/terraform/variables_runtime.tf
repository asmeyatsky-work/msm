# Runtime knobs surfaced as Terraform variables so the same module deploys
# staging and prod with env-appropriate values via -var-file=envs/<env>.tfvars.
# Defaults are PRD §5 prod-shaped; staging.tfvars relaxes them.

variable "anomaly_threshold" {
  description = "PRD §5 null/zero rate that trips the breaker. Prod default 0.03; staging relaxed because synthetic data extrapolates negatively."
  type        = number
  default     = 0.03
}

variable "anomaly_window_secs" {
  description = "Sliding window length for AnomalyWindow."
  type        = number
  default     = 300
}

variable "anomaly_min_samples" {
  description = "Floor on samples before AnomalyWindow.breached() can trip — prevents low-traffic spikes from flipping the breaker."
  type        = number
  default     = 50
}

variable "model_timeout_ms" {
  description = "Per-call Vertex AI predict timeout."
  type        = number
  default     = 500
}

variable "bq_timeout_ms" {
  description = "Per-call BigQuery fallback timeout."
  type        = number
  default     = 500
}

variable "scoring_api_min_instances" {
  description = "Cloud Run min instances for scoring-api. Prod defaults to 2 for redundancy; staging tfvars overrides to 1."
  type        = number
  default     = 2
}

variable "scoring_api_max_instances" {
  description = "Cloud Run max instances for scoring-api."
  type        = number
  default     = 50
}

variable "scoring_api_concurrency" {
  description = "Cloud Run per-instance concurrency for scoring-api. Tune from Phase 1.5 load profile."
  type        = number
  default     = 80
}

variable "scoring_api_p95_threshold_ms" {
  description = "Cloud Run p95 request_latencies alert threshold for scoring-api. Set from Phase 1.5 load profile (score p95 ~920ms on e2-standard-2 + xgboost-cpu.1-7); add headroom."
  type        = number
  default     = 1500
}
