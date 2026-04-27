# Cloud Monitoring alerts + log-based metrics + SLO (Phase 3.4).
# §5: Observability is a guardrail, not a nice-to-have. Alerts here are the
# minimum that lets oncall act before a breaker trip turns into ledger drift.

variable "alert_notification_channels" {
  description = "Cloud Monitoring notification channel IDs (full resource paths). Empty list = alerts fire silently in the console; wire an email/Slack channel before going to prod."
  type        = list(string)
  default     = []
}

# --- Log-based metric: scoring-api breaker trips ------------------------------
# Counts the structured "anomaly window breached" warning emitted by the
# AnomalyWindow path in score_click.rs. Goes hot the moment >threshold of
# predictions are null/zero in the sliding window.
resource "google_logging_metric" "breaker_trips" {
  name        = "scoring_api_breaker_trips_${var.env}"
  description = "Count of breaker trips on scoring-api (anomaly window breached)."
  filter      = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="scoring-api-${var.env}"
    severity>=WARNING
    jsonPayload.message=~"anomaly window breached"
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# --- Alert: scoring-api 5xx rate (availability SLI) ---------------------------
resource "google_monitoring_alert_policy" "scoring_api_5xx" {
  display_name          = "scoring-api ${var.env} — 5xx rate > 1% (5m)"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "5xx rate over 1%"
    condition_threshold {
      filter          = <<-EOT
        resource.type="cloud_run_revision"
        resource.labels.service_name="scoring-api-${var.env}"
        metric.type="run.googleapis.com/request_count"
        metric.labels.response_code_class="5xx"
      EOT
      comparison      = "COMPARISON_GT"
      threshold_value = 0.01
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Runbook: docs/runbooks/breaker-reset.md. First check `/health`, then breaker state via `runtime_config_${var.env}` secret."
  }
}

# --- Alert: scoring-api p95 latency -------------------------------------------
# PRD §2.2 budget on the request path is 100ms total; alert at 250ms p95
# because Vertex round-trip dominates and varies. Tighten from Phase 1.5.
resource "google_monitoring_alert_policy" "scoring_api_p95_latency" {
  display_name          = "scoring-api ${var.env} — p95 latency > 250ms (5m)"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "p95 over 250ms"
    condition_threshold {
      filter          = <<-EOT
        resource.type="cloud_run_revision"
        resource.labels.service_name="scoring-api-${var.env}"
        metric.type="run.googleapis.com/request_latencies"
      EOT
      comparison      = "COMPARISON_GT"
      threshold_value = 250
      duration        = "300s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_PERCENTILE_95"
        cross_series_reducer = "REDUCE_MEAN"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Vertex AI predict latency drives this. Check `vertex-endpoint-url-${var.env}` health and recent model deploys."
  }
}

# --- Alert: breaker trip in the last 5 minutes --------------------------------
resource "google_monitoring_alert_policy" "scoring_api_breaker_tripped" {
  display_name          = "scoring-api ${var.env} — anomaly breaker tripped"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "any trip in last 5m"
    condition_threshold {
      filter          = <<-EOT
        metric.type="logging.googleapis.com/user/${google_logging_metric.breaker_trips.name}"
        resource.type="cloud_run_revision"
      EOT
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Sliding anomaly window breached — predictions falling back to data layer. Runbook: docs/runbooks/breaker-reset.md."
  }
}

# --- Alert: Pub/Sub predictions backlog ---------------------------------------
# Predictions topic feeds the BQ subscription; if the subscription stalls,
# Shadow Production data dries up.
resource "google_monitoring_alert_policy" "predictions_backlog" {
  display_name          = "rpc-predictions ${var.env} — BQ sub backlog > 10k"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "undelivered messages > 10k"
    condition_threshold {
      filter          = <<-EOT
        resource.type="pubsub_subscription"
        resource.labels.subscription_id="${google_pubsub_subscription.predictions_to_bq.name}"
        metric.type="pubsub.googleapis.com/subscription/num_undelivered_messages"
      EOT
      comparison      = "COMPARISON_GT"
      threshold_value = 10000
      duration        = "600s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "BQ subscription not draining. Check Pub/Sub→BQ permissions and recent terraform applies."
  }
}

# --- Service-level objective: scoring-api availability ------------------------
# 99.5% prod SLO over a rolling 30-day window. Doubles as the availability SLI
# for the error-budget conversation.
resource "google_monitoring_custom_service" "scoring_api" {
  service_id   = "scoring-api-${var.env}"
  display_name = "scoring-api (${var.env})"
}

resource "google_monitoring_slo" "scoring_api_availability" {
  service             = google_monitoring_custom_service.scoring_api.service_id
  slo_id              = "scoring-api-availability-${var.env}"
  display_name        = "scoring-api availability ≥ 99.5% (30d)"
  goal                = 0.995
  rolling_period_days = 30

  request_based_sli {
    good_total_ratio {
      good_service_filter  = <<-EOT
        resource.type="cloud_run_revision"
        resource.labels.service_name="scoring-api-${var.env}"
        metric.type="run.googleapis.com/request_count"
        metric.labels.response_code_class="2xx"
      EOT
      total_service_filter = <<-EOT
        resource.type="cloud_run_revision"
        resource.labels.service_name="scoring-api-${var.env}"
        metric.type="run.googleapis.com/request_count"
      EOT
    }
  }
}
