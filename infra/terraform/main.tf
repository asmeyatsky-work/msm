# Predictive RPC Estimator — GCP IaC (PRD §4.1 "Design & Build" gate).
# §4: Secret Manager + Workload Identity only. No secret values in this file.

terraform {
  required_version = ">= 1.8.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.35"
    }
  }
  backend "gcs" {}
}

variable "project_id" {
  type = string
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "env" {
  type = string
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --- Data foundation (PRD §2.2) ---
resource "google_bigquery_dataset" "rpc" {
  dataset_id  = "rpc_estimator_${var.env}"
  location    = var.region
  description = "Predictive RPC Estimator sales ledger, click exports, and rolling features."
}

resource "google_storage_bucket" "artifacts" {
  name                        = "${var.project_id}-rpc-artifacts-${var.env}"
  location                    = var.region
  uniform_bucket_level_access = true
  versioning {
    enabled = true
  }
}

# --- Event backbone (PRD §2.2) ---
resource "google_pubsub_topic" "predictions" {
  name = "rpc-predictions-${var.env}"
}

# Shadow Production sink (PRD §4.2): Pub/Sub → BigQuery predictions table.
resource "google_bigquery_table" "predictions" {
  dataset_id = google_bigquery_dataset.rpc.dataset_id
  table_id   = "rpc_predictions"
  time_partitioning {
    type  = "DAY"
    field = "predicted_at"
  }
  schema = jsonencode([
    { name = "click_id", type = "STRING", mode = "REQUIRED" },
    { name = "correlation_id", type = "STRING", mode = "NULLABLE" },
    { name = "predicted_rpc", type = "FLOAT64", mode = "REQUIRED" },
    { name = "source", type = "STRING", mode = "REQUIRED" },
    { name = "model_version", type = "STRING", mode = "NULLABLE" },
    { name = "ts_ms", type = "INT64", mode = "REQUIRED" },
    { name = "predicted_at", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_pubsub_subscription" "predictions_to_bq" {
  name  = "rpc-predictions-bq-${var.env}"
  topic = google_pubsub_topic.predictions.name

  bigquery_config {
    table               = "${var.project_id}.${google_bigquery_dataset.rpc.dataset_id}.${google_bigquery_table.predictions.table_id}"
    use_topic_schema    = false
    write_metadata      = false
    drop_unknown_fields = true
  }
}

resource "google_pubsub_topic" "audit" {
  name = "rpc-audit-${var.env}"
  # §4: append-only; separate IAM attached out-of-band to `rpc-audit-writer` SA.
}

# --- Service accounts + Workload Identity (§4) ---
resource "google_service_account" "scoring_api" {
  account_id   = "scoring-api-${var.env}"
  display_name = "Scoring API (Cloud Run) — Workload Identity"
}

resource "google_service_account" "activation" {
  account_id   = "activation-${var.env}"
  display_name = "Activation bridge"
}

# --- Secrets (§4: never in code/config) ---
resource "google_secret_manager_secret" "ssgtm_api_key" {
  secret_id = "ssgtm-api-key-${var.env}"
  replication {
    auto {}
  }
}

# --- Runtime config (PRD §5 Kill Switch without redeploy) ---
resource "google_secret_manager_secret" "runtime_config" {
  secret_id = "rpc-runtime-config-${var.env}"
  replication {
    auto {}
  }
}

# Initial runtime config — scoring-api fails startup without a version to read.
# Starting posture: kill off, full canary, bounds matching the hardcoded env
# defaults. Staged rollout narrows canary_bp through Cloud Scheduler later.
resource "google_secret_manager_secret_version" "runtime_config_initial" {
  secret = google_secret_manager_secret.runtime_config.id
  secret_data = jsonencode({
    kill       = false
    bounds_min = 0.01
    bounds_max = 500.0
    canary_bp  = 10000 # PRD §4.3: start at 100% = shadow mode by bounds only
  })

  # Subsequent versions are written by the breaker-automation Cloud Function
  # (kill switch) and by the bounds-calibration job (bounds_min/max) via PR
  # merge. Don't let `terraform apply` overwrite them.
  lifecycle {
    ignore_changes = [secret_data, enabled]
  }
}

# --- Circuit breaker automation (PRD §2.2 Cloud Functions) ---
resource "google_pubsub_topic" "alerts_anomaly" {
  name = "rpc-anomaly-${var.env}"
}

# --- Breaker automation (PRD §5 automated circuit breaker) ---
# Cloud Function subscribes to rpc-anomaly and writes a new Secret Manager
# version of runtime_config; scoring-api re-reads it on its refresh cadence.
resource "google_service_account" "breaker_automation" {
  account_id   = "breaker-automation-${var.env}"
  display_name = "Breaker automation (Cloud Function)"
}

resource "google_secret_manager_secret_iam_member" "breaker_writer" {
  secret_id = google_secret_manager_secret.runtime_config.id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.breaker_automation.email}"
}

resource "google_secret_manager_secret_iam_member" "scoring_api_reader" {
  secret_id = google_secret_manager_secret.runtime_config.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.scoring_api.email}"
}

# Cloud Run services (scoring-api, activation) are deployed by CI with images
# built from `services/scoring-api` and `services/activation`. Wiring here keeps
# the infrastructure declarative and auditable.
