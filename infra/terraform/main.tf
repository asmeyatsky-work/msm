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

# Shadow Production sink (PRD §4.2).
# Pub/Sub→BQ default schema: raw `data` STRING column; a view unpacks JSON.
resource "google_bigquery_table" "predictions" {
  dataset_id          = google_bigquery_dataset.rpc.dataset_id
  table_id            = "rpc_predictions_raw"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "publish_time"
  }
  schema = jsonencode([
    { name = "subscription_name", type = "STRING", mode = "NULLABLE" },
    { name = "message_id", type = "STRING", mode = "NULLABLE" },
    { name = "publish_time", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "data", type = "STRING", mode = "NULLABLE" },
    { name = "attributes", type = "STRING", mode = "NULLABLE" },
  ])
}

# Typed view over the raw Pub/Sub table — keeps the reconciliation contract stable.
# Sales ledger — realized revenue per click. BigQueryDataLayer queries this
# on circuit-breaker fallback (PRD §5). Empty at bootstrap; Dataform / the
# ingestion job appends rows.
resource "google_bigquery_table" "sales_ledger" {
  dataset_id          = google_bigquery_dataset.rpc.dataset_id
  table_id            = "sales_ledger"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "revenue_ts"
  }
  schema = jsonencode([
    { name = "click_id", type = "STRING", mode = "REQUIRED" },
    { name = "revenue", type = "FLOAT64", mode = "REQUIRED" },
    { name = "revenue_ts", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "order_id", type = "STRING", mode = "NULLABLE" },
    { name = "ts_ms", type = "INT64", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "predictions_view" {
  dataset_id          = google_bigquery_dataset.rpc.dataset_id
  table_id            = "rpc_predictions"
  deletion_protection = false
  view {
    query          = <<-SQL
      SELECT
        JSON_EXTRACT_SCALAR(data, '$.click_id')       AS click_id,
        JSON_EXTRACT_SCALAR(data, '$.correlation_id') AS correlation_id,
        CAST(JSON_EXTRACT_SCALAR(data, '$.predicted_rpc') AS FLOAT64) AS predicted_rpc,
        JSON_EXTRACT_SCALAR(data, '$.source')         AS source,
        JSON_EXTRACT_SCALAR(data, '$.model_version')  AS model_version,
        CAST(JSON_EXTRACT_SCALAR(data, '$.ts_ms') AS INT64) AS ts_ms,
        publish_time                                   AS predicted_at
      FROM `${var.project_id}.${google_bigquery_dataset.rpc.dataset_id}.rpc_predictions_raw`
    SQL
    use_legacy_sql = false
  }
  depends_on = [google_bigquery_table.predictions]
}

# Pub/Sub service agent needs BQ write + metadata read to hydrate the sink.
resource "google_project_iam_member" "pubsub_bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "pubsub_bq_metadata" {
  project = var.project_id
  role    = "roles/bigquery.metadataViewer"
  member  = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription" "predictions_to_bq" {
  name  = "rpc-predictions-bq-${var.env}"
  topic = google_pubsub_topic.predictions.name

  depends_on = [
    google_project_iam_member.pubsub_bq_data_editor,
    google_project_iam_member.pubsub_bq_metadata,
  ]

  bigquery_config {
    table               = "${var.project_id}.${google_bigquery_dataset.rpc.dataset_id}.${google_bigquery_table.predictions.table_id}"
    use_topic_schema    = false
    write_metadata      = true   # required so publish_time / message_id columns get filled
    drop_unknown_fields = true
  }
}

resource "google_pubsub_topic" "audit" {
  name = "rpc-audit-${var.env}"
  # §4: append-only; separate IAM attached out-of-band to `rpc-audit-writer` SA.
}

# --- Click ingestion stream (Phase 2.2) ---
# Client publishes one message per click to rpc-clicks-${env}; a BigQuery
# subscription lands the JSON in cm360_clicks_raw, and a typed view exposes
# the data-contract schema (docs/data-contract.md §2.1) as cm360_clicks for
# Dataform / training to consume.
resource "google_pubsub_topic" "clicks" {
  name = "rpc-clicks-${var.env}"
}

resource "google_bigquery_table" "clicks_raw" {
  dataset_id          = google_bigquery_dataset.rpc.dataset_id
  table_id            = "cm360_clicks_raw"
  deletion_protection = false
  time_partitioning {
    type  = "DAY"
    field = "publish_time"
  }
  schema = jsonencode([
    { name = "subscription_name", type = "STRING", mode = "NULLABLE" },
    { name = "message_id", type = "STRING", mode = "NULLABLE" },
    { name = "publish_time", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "data", type = "STRING", mode = "NULLABLE" },
    { name = "attributes", type = "STRING", mode = "NULLABLE" },
  ])
}

resource "google_bigquery_table" "clicks_view" {
  dataset_id          = google_bigquery_dataset.rpc.dataset_id
  table_id            = "cm360_clicks"
  deletion_protection = false
  view {
    query          = <<-SQL
      SELECT
        JSON_EXTRACT_SCALAR(data, '$.click_id')        AS click_id,
        TIMESTAMP(JSON_EXTRACT_SCALAR(data, '$.click_ts')) AS click_ts,
        JSON_EXTRACT_SCALAR(data, '$.device')          AS device,
        JSON_EXTRACT_SCALAR(data, '$.geo')             AS geo,
        CAST(JSON_EXTRACT_SCALAR(data, '$.hour_of_day') AS INT64) AS hour_of_day,
        JSON_EXTRACT_SCALAR(data, '$.query_intent')    AS query_intent,
        JSON_EXTRACT_SCALAR(data, '$.ad_creative_id')  AS ad_creative_id,
        CAST(JSON_EXTRACT_SCALAR(data, '$.cerberus_score')   AS FLOAT64) AS cerberus_score,
        CAST(JSON_EXTRACT_SCALAR(data, '$.rpc_7d')           AS FLOAT64) AS rpc_7d,
        CAST(JSON_EXTRACT_SCALAR(data, '$.rpc_14d')          AS FLOAT64) AS rpc_14d,
        CAST(JSON_EXTRACT_SCALAR(data, '$.rpc_30d')          AS FLOAT64) AS rpc_30d,
        CAST(JSON_EXTRACT_SCALAR(data, '$.is_payday_week')   AS BOOL)    AS is_payday_week,
        CAST(JSON_EXTRACT_SCALAR(data, '$.auction_pressure') AS FLOAT64) AS auction_pressure,
        JSON_EXTRACT_SCALAR(data, '$.landing_path')          AS landing_path,
        CAST(JSON_EXTRACT_SCALAR(data, '$.visits_prev_30d')  AS INT64)   AS visits_prev_30d,
        publish_time                                                      AS ingested_at
      FROM `${var.project_id}.${google_bigquery_dataset.rpc.dataset_id}.cm360_clicks_raw`
    SQL
    use_legacy_sql = false
  }
  depends_on = [google_bigquery_table.clicks_raw]
}

resource "google_pubsub_subscription" "clicks_to_bq" {
  name  = "rpc-clicks-bq-${var.env}"
  topic = google_pubsub_topic.clicks.name

  depends_on = [
    google_project_iam_member.pubsub_bq_data_editor,
    google_project_iam_member.pubsub_bq_metadata,
  ]

  bigquery_config {
    table               = "${var.project_id}.${google_bigquery_dataset.rpc.dataset_id}.${google_bigquery_table.clicks_raw.table_id}"
    use_topic_schema    = false
    write_metadata      = true
    drop_unknown_fields = true
  }
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

resource "google_secret_manager_secret" "vertex_endpoint_url" {
  secret_id = "vertex-endpoint-url-${var.env}"
  replication {
    auto {}
  }
}

# Placeholder Vertex endpoint URL — first deploy just needs scoring-api to
# boot. Replace the secret value once a real model is registered.
resource "google_secret_manager_secret_version" "vertex_endpoint_url_initial" {
  secret      = google_secret_manager_secret.vertex_endpoint_url.id
  secret_data = "https://vertex-placeholder.example.com/predict"
  lifecycle {
    ignore_changes = [secret_data, enabled]
  }
}

resource "google_secret_manager_secret_iam_member" "scoring_api_vertex_url" {
  secret_id = google_secret_manager_secret.vertex_endpoint_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.scoring_api.email}"
}

# --- Runtime IAM for scoring-api SA (previously granted out-of-band) ---
# scoring-api calls Vertex AI online prediction (§2.2) and reads BigQuery on
# the breaker fallback path (§5). These were granted ad-hoc during first
# deploy; codifying so a fresh-project bootstrap reproduces the live state.
resource "google_project_iam_member" "scoring_api_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.scoring_api.email}"
}

resource "google_project_iam_member" "scoring_api_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.scoring_api.email}"
}

resource "google_bigquery_dataset_iam_member" "scoring_api_bq_data_viewer" {
  dataset_id = google_bigquery_dataset.rpc.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.scoring_api.email}"
}

# Vertex AI Service Agent reads model artifacts from this bucket during
# model upload / deployment. Granted out-of-band on first deploy.
resource "google_storage_bucket_iam_member" "vertex_sa_artifacts_reader" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
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
