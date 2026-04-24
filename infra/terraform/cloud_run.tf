# Cloud Run services (PRD §2.2). Images pushed by CI to Artifact Registry.
# §4: Workload Identity only; no service-account keys.

variable "image_scoring_api"     { type = string }
variable "image_reconciliation"  { type = string }
variable "image_activation"      { type = string }
variable "image_breaker"         { type = string }
variable "image_ml_pipeline"     { type = string }

locals {
  otel_endpoint = "https://telemetry.googleapis.com:443"
}

resource "google_cloud_run_v2_service" "scoring_api" {
  name     = "scoring-api-${var.env}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.scoring_api.email
    # Hot path: preserve CPU to avoid cold-start p99 hits.
    scaling { min_instance_count = 1 max_instance_count = 50 }
    containers {
      image = var.image_scoring_api
      ports { container_port = 8080 }
      resources {
        limits = { cpu = "2", memory = "1Gi" }
        cpu_idle = false
        startup_cpu_boost = true
      }
      env { name = "GCP_PROJECT"             value = var.project_id }
      env { name = "BQ_DATASET"              value = google_bigquery_dataset.rpc.dataset_id }
      env { name = "PREDICTIONS_TOPIC"       value = google_pubsub_topic.predictions.name }
      env { name = "RUNTIME_CONFIG_SECRET"   value = google_secret_manager_secret.runtime_config.secret_id }
      env { name = "OTEL_EXPORTER_OTLP_ENDPOINT" value = local.otel_endpoint }
      env {
        name = "VERTEX_ENDPOINT_URL"
        value_source { secret_key_ref {
          secret  = "vertex-endpoint-url-${var.env}"
          version = "latest"
        }}
      }
    }
  }
}

resource "google_cloud_run_v2_service" "reconciliation" {
  name     = "reconciliation-${var.env}"
  location = var.region
  template {
    service_account = google_service_account.scoring_api.email
    containers {
      image = var.image_reconciliation
      ports { container_port = 8080 }
      env { name = "GCP_PROJECT" value = var.project_id }
      env { name = "BQ_DATASET"  value = google_bigquery_dataset.rpc.dataset_id }
    }
  }
}

# Activation: push-based Pub/Sub subscriber → Cloud Run job-style service.
resource "google_cloud_run_v2_service" "activation" {
  name     = "activation-${var.env}"
  location = var.region
  template {
    service_account = google_service_account.activation.email
    containers { image = var.image_activation }
  }
}

# Breaker-automation: 2nd-gen Cloud Function deployed as Cloud Run v2 service
# with a Pub/Sub push subscription to rpc-anomaly.
resource "google_cloud_run_v2_service" "breaker_automation" {
  name     = "breaker-automation-${var.env}"
  location = var.region
  template {
    service_account = google_service_account.breaker_automation.email
    containers {
      image = var.image_breaker
      env { name = "GCP_PROJECT"            value = var.project_id }
      env { name = "RUNTIME_CONFIG_SECRET"  value = google_secret_manager_secret.runtime_config.secret_id }
    }
  }
}

resource "google_pubsub_subscription" "anomaly_to_breaker" {
  name  = "rpc-anomaly-to-breaker-${var.env}"
  topic = google_pubsub_topic.alerts_anomaly.name

  push_config {
    push_endpoint = google_cloud_run_v2_service.breaker_automation.uri
    oidc_token { service_account_email = google_service_account.breaker_automation.email }
  }
  ack_deadline_seconds = 30
}

# Bounds auto-calibration — scheduled PR opener. Optional (gated on image var).
variable "image_bounds_calibration" {
  type    = string
  default = ""
}

resource "google_cloud_run_v2_job" "bounds_calibration" {
  count    = var.image_bounds_calibration == "" ? 0 : 1
  name     = "bounds-calibration-${var.env}"
  location = var.region
  template {
    template {
      service_account = google_service_account.scoring_api.email
      containers {
        image = var.image_bounds_calibration
        env { name = "GCP_PROJECT" value = var.project_id }
        env { name = "BQ_DATASET"  value = google_bigquery_dataset.rpc.dataset_id }
      }
    }
  }
}

resource "google_cloud_scheduler_job" "bounds_calibration" {
  count    = var.image_bounds_calibration == "" ? 0 : 1
  name     = "bounds-calibration-${var.env}"
  schedule = "0 6 * * 1"  # Mondays 06:00 UTC
  region   = var.region
  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.bounds_calibration[0].name}:run"
    oauth_token { service_account_email = google_service_account.scoring_api.email }
  }
}

# ml-pipeline runs on Cloud Run Jobs (training is not a long-lived service).
resource "google_cloud_run_v2_job" "ml_pipeline_train" {
  name     = "ml-pipeline-train-${var.env}"
  location = var.region
  template {
    template {
      service_account = google_service_account.scoring_api.email
      containers {
        image = var.image_ml_pipeline
        args  = ["train", "--project", var.project_id, "--dataset", google_bigquery_dataset.rpc.dataset_id]
      }
    }
  }
}
