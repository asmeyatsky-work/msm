# Reasoning agents (ADR 0005) — Cloud Run self-hosted, triggered by Pub/Sub
# (breaker) and Cloud Scheduler (bounds, drift). Gemini is reached via API key
# (Google AI), so this is region-independent and sidesteps the EU Vertex
# model-availability limits in europe-west2.
#
# Everything here is gated on `deploy_agents` (default false) AND the per-agent
# image var being set, mirroring the DEPLOY_PROD / DEPLOY_CLIENT_CC opt-in
# pattern — nothing is created (and no cost accrues) until you flip it on.

variable "deploy_agents" {
  description = "Opt-in: deploy the three reasoning agents (breaker triage, bounds calibration, drift triage) to Cloud Run."
  type        = bool
  default     = false
}

variable "image_breaker_agent" {
  type    = string
  default = ""
}
variable "image_bounds_agent" {
  type    = string
  default = ""
}
variable "image_drift_agent" {
  type    = string
  default = ""
}

variable "agents_github_repo" {
  description = "owner/name the bounds agent opens recalibration PRs against."
  type        = string
  default     = "asmeyatsky-work/msm"
}
variable "agents_bounds_current_min" {
  type    = number
  default = 0.01
}
variable "agents_bounds_current_max" {
  type    = number
  default = 500.0
}

locals {
  breaker_agent_on = var.deploy_agents && var.image_breaker_agent != "" ? 1 : 0
  bounds_agent_on  = var.deploy_agents && var.image_bounds_agent != "" ? 1 : 0
  drift_agent_on   = var.deploy_agents && var.image_drift_agent != "" ? 1 : 0
  any_agent_on     = var.deploy_agents ? 1 : 0
}

# --- Shared secrets (§4) -------------------------------------------------------
# Gemini API key for all three agents. Placeholder version so apply succeeds;
# replace the value out-of-band before the agents are useful (ignore_changes).
resource "google_secret_manager_secret" "gemini_api_key" {
  count     = local.any_agent_on
  secret_id = "gemini-api-key-${var.env}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "gemini_api_key_initial" {
  count       = local.any_agent_on
  secret      = google_secret_manager_secret.gemini_api_key[0].id
  secret_data = "REPLACE_ME"
  lifecycle {
    ignore_changes = [secret_data, enabled]
  }
}

# GitHub token for the bounds agent's PR gateway.
resource "google_secret_manager_secret" "github_token" {
  count     = local.bounds_agent_on
  secret_id = "github-token-${var.env}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "github_token_initial" {
  count       = local.bounds_agent_on
  secret      = google_secret_manager_secret.github_token[0].id
  secret_data = "REPLACE_ME"
  lifecycle {
    ignore_changes = [secret_data, enabled]
  }
}

# Incident topic the breaker triage agent publishes escalations to.
resource "google_pubsub_topic" "incidents" {
  count = local.breaker_agent_on
  name  = "rpc-incidents-${var.env}"
}

# =============================================================================
# Breaker triage agent
# =============================================================================
resource "google_service_account" "breaker_agent" {
  count        = local.breaker_agent_on
  account_id   = "breaker-agent-${var.env}"
  display_name = "Breaker triage agent (Cloud Run)"
}

resource "google_project_iam_member" "breaker_agent_bq_job_user" {
  count   = local.breaker_agent_on
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.breaker_agent[0].email}"
}

resource "google_bigquery_dataset_iam_member" "breaker_agent_bq_viewer" {
  count      = local.breaker_agent_on
  dataset_id = google_bigquery_dataset.rpc.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.breaker_agent[0].email}"
}

resource "google_pubsub_topic_iam_member" "breaker_agent_incidents_publisher" {
  count  = local.breaker_agent_on
  topic  = google_pubsub_topic.incidents[0].name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.breaker_agent[0].email}"
}

resource "google_secret_manager_secret_iam_member" "breaker_agent_gemini" {
  count     = local.breaker_agent_on
  secret_id = google_secret_manager_secret.gemini_api_key[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.breaker_agent[0].email}"
}

resource "google_cloud_run_v2_service" "breaker_agent" {
  count    = local.breaker_agent_on
  name     = "breaker-agent-${var.env}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.breaker_agent[0].email
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    # LLM calls take tens of seconds; give the request room.
    timeout = "120s"
    containers {
      image = var.image_breaker_agent
      ports {
        container_port = 8080
      }
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET"
        value = google_bigquery_dataset.rpc.dataset_id
      }
      env {
        name  = "INCIDENT_TOPIC"
        value = google_pubsub_topic.incidents[0].name
      }
      env {
        name = "GOOGLE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key[0].secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

# Pub/Sub push: the agent triages every anomaly in parallel with the
# deterministic trip Cloud Function (separate subscription on the same topic).
resource "google_cloud_run_v2_service_iam_member" "breaker_agent_invoker" {
  count    = local.breaker_agent_on
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.breaker_agent[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.breaker_agent[0].email}"
}

resource "google_pubsub_subscription" "anomaly_to_breaker_agent" {
  count = local.breaker_agent_on
  name  = "rpc-anomaly-to-breaker-agent-${var.env}"
  topic = google_pubsub_topic.alerts_anomaly.name
  push_config {
    push_endpoint = google_cloud_run_v2_service.breaker_agent[0].uri
    oidc_token {
      service_account_email = google_service_account.breaker_agent[0].email
    }
  }
  ack_deadline_seconds = 120
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# =============================================================================
# Bounds calibration agent
# =============================================================================
resource "google_service_account" "bounds_agent" {
  count        = local.bounds_agent_on
  account_id   = "bounds-agent-${var.env}"
  display_name = "Bounds calibration agent (Cloud Run)"
}

resource "google_project_iam_member" "bounds_agent_bq_job_user" {
  count   = local.bounds_agent_on
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.bounds_agent[0].email}"
}

resource "google_bigquery_dataset_iam_member" "bounds_agent_bq_viewer" {
  count      = local.bounds_agent_on
  dataset_id = google_bigquery_dataset.rpc.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.bounds_agent[0].email}"
}

resource "google_secret_manager_secret_iam_member" "bounds_agent_gemini" {
  count     = local.bounds_agent_on
  secret_id = google_secret_manager_secret.gemini_api_key[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.bounds_agent[0].email}"
}

resource "google_secret_manager_secret_iam_member" "bounds_agent_github" {
  count     = local.bounds_agent_on
  secret_id = google_secret_manager_secret.github_token[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.bounds_agent[0].email}"
}

resource "google_cloud_run_v2_service" "bounds_agent" {
  count    = local.bounds_agent_on
  name     = "bounds-agent-${var.env}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.bounds_agent[0].email
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    timeout = "120s"
    containers {
      image = var.image_bounds_agent
      ports {
        container_port = 8080
      }
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET"
        value = google_bigquery_dataset.rpc.dataset_id
      }
      env {
        name  = "GITHUB_REPO"
        value = var.agents_github_repo
      }
      env {
        name  = "CONFIG_PATH"
        value = "infra/runtime_config.json"
      }
      env {
        name  = "LOOKBACK_HOURS"
        value = "168"
      }
      env {
        name  = "CURRENT_MIN"
        value = tostring(var.agents_bounds_current_min)
      }
      env {
        name  = "CURRENT_MAX"
        value = tostring(var.agents_bounds_current_max)
      }
      env {
        name = "GOOGLE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key[0].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GITHUB_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.github_token[0].secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "bounds_agent_invoker" {
  count    = local.bounds_agent_on
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.bounds_agent[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.bounds_agent[0].email}"
}

resource "google_cloud_scheduler_job" "bounds_agent" {
  count    = local.bounds_agent_on
  name     = "bounds-agent-${var.env}"
  schedule = "0 6 * * 1" # Mondays 06:00 UTC (mirrors the deterministic Job cadence)
  region   = var.region
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.bounds_agent[0].uri}/"
    oidc_token {
      service_account_email = google_service_account.bounds_agent[0].email
      audience              = google_cloud_run_v2_service.bounds_agent[0].uri
    }
  }
}

# =============================================================================
# Drift triage agent
# =============================================================================
resource "google_service_account" "drift_agent" {
  count        = local.drift_agent_on
  account_id   = "drift-agent-${var.env}"
  display_name = "Drift triage agent (Cloud Run)"
}

resource "google_project_iam_member" "drift_agent_bq_job_user" {
  count   = local.drift_agent_on
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.drift_agent[0].email}"
}

resource "google_bigquery_dataset_iam_member" "drift_agent_bq_viewer" {
  count      = local.drift_agent_on
  dataset_id = google_bigquery_dataset.rpc.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.drift_agent[0].email}"
}

# registry.latest reads the Vertex model registry.
resource "google_project_iam_member" "drift_agent_aiplatform" {
  count   = local.drift_agent_on
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.drift_agent[0].email}"
}

# RETRAIN fires the ml-pipeline-train Cloud Run Job.
resource "google_cloud_run_v2_job_iam_member" "drift_agent_train_invoker" {
  count    = local.drift_agent_on
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.ml_pipeline_train.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.drift_agent[0].email}"
}

resource "google_secret_manager_secret_iam_member" "drift_agent_gemini" {
  count     = local.drift_agent_on
  secret_id = google_secret_manager_secret.gemini_api_key[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.drift_agent[0].email}"
}

resource "google_cloud_run_v2_service" "drift_agent" {
  count    = local.drift_agent_on
  name     = "drift-agent-${var.env}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  template {
    service_account = google_service_account.drift_agent[0].email
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    timeout = "120s"
    containers {
      image = var.image_drift_agent
      ports {
        container_port = 8080
      }
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET"
        value = google_bigquery_dataset.rpc.dataset_id
      }
      env {
        name  = "VERTEX_REGION"
        value = var.region
      }
      env {
        name  = "STAGING_BUCKET"
        value = "gs://${google_storage_bucket.artifacts.name}"
      }
      env {
        name  = "MODEL_ID"
        value = "rpc-estimator"
      }
      # Present => RETRAIN triggers this Job instead of training in-process.
      env {
        name  = "ML_TRAIN_JOB"
        value = google_cloud_run_v2_job.ml_pipeline_train.name
      }
      env {
        name = "GOOGLE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key[0].secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "drift_agent_invoker" {
  count    = local.drift_agent_on
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.drift_agent[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.drift_agent[0].email}"
}

resource "google_cloud_scheduler_job" "drift_agent" {
  count    = local.drift_agent_on
  name     = "drift-agent-${var.env}"
  schedule = "30 6 * * *" # daily 06:30 UTC, after dataform materializes psi_daily
  region   = var.region
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.drift_agent[0].uri}/"
    oidc_token {
      service_account_email = google_service_account.drift_agent[0].email
      audience              = google_cloud_run_v2_service.drift_agent[0].uri
    }
  }
}

# --- Outputs -------------------------------------------------------------------
output "breaker_agent_url" {
  value = local.breaker_agent_on == 1 ? google_cloud_run_v2_service.breaker_agent[0].uri : ""
}
output "bounds_agent_url" {
  value = local.bounds_agent_on == 1 ? google_cloud_run_v2_service.bounds_agent[0].uri : ""
}
output "drift_agent_url" {
  value = local.drift_agent_on == 1 ? google_cloud_run_v2_service.drift_agent[0].uri : ""
}
