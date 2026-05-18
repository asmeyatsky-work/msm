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
# PRD §2.2 budget on the request path is 100ms total, but Vertex AI predict
# round-trip dominates (~700ms p50 / ~920ms p95 on e2-standard-2 +
# xgboost-cpu.1-7 measured 2026-04-28). Threshold is var-driven so prod can
# tighten it once on a larger Vertex machine.
resource "google_monitoring_alert_policy" "scoring_api_p95_latency" {
  display_name          = "scoring-api ${var.env} — p95 latency > ${var.scoring_api_p95_threshold_ms}ms (5m)"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "p95 over ${var.scoring_api_p95_threshold_ms}ms"
    condition_threshold {
      filter          = <<-EOT
        resource.type="cloud_run_revision"
        resource.labels.service_name="scoring-api-${var.env}"
        metric.type="run.googleapis.com/request_latencies"
      EOT
      comparison      = "COMPARISON_GT"
      threshold_value = var.scoring_api_p95_threshold_ms
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

# --- PRD V2 §4.6 — CC drift + coverage alerts ---------------------------------
# Per-segment residual MAE drift > 25% W-o-W and per-slice coverage drop > 10%
# W-o-W. The breach detection is materialised by Dataform in two tables:
#   * rpc_estimator.drift_breaches_weekly
#   * rpc_estimator.coverage_drops_weekly
# A daily emitter (ops/breach_emitter.py, scheduled via Cloud Scheduler →
# breaker-automation) writes one structured-log line per breach row with
# the field jsonPayload.alert.kind set to "drift_breach" or "coverage_drop".
# The two log-based metrics below count those lines; the alert policies
# fire when the count crosses 0 within the alignment window.
#
# Until the emitter is scheduled the metrics stay at zero and the policies
# are silent — same pattern as breaker_trips. This means the alerting
# *structure* is deployable today; flipping it on is a Cloud Scheduler
# addition once a notification channel is wired (OQ-2 / OQ-9).

resource "google_logging_metric" "drift_breaches" {
  name        = "rpc_drift_breaches_${var.env}"
  description = "Count of per-segment MAE drift breaches emitted by the breach scanner (ops/breach_emitter.py)."
  filter      = <<-EOT
    logName="projects/${var.project_id}/logs/rpc-breach-emitter-${var.env}"
    severity>=WARNING
    jsonPayload.alert.kind="drift_breach"
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "product_type"
      value_type  = "STRING"
      description = "PRD V2 §7.1 product_type of the breaching segment."
    }
  }
  label_extractors = {
    "product_type" = "EXTRACT(jsonPayload.alert.product_type)"
  }
}

resource "google_logging_metric" "coverage_drops" {
  name        = "rpc_coverage_drops_${var.env}"
  description = "Count of per-slice coverage drops emitted by the breach scanner (ops/breach_emitter.py)."
  filter      = <<-EOT
    logName="projects/${var.project_id}/logs/rpc-breach-emitter-${var.env}"
    severity>=WARNING
    jsonPayload.alert.kind="coverage_drop"
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "slice_dim"
      value_type  = "STRING"
      description = "Dimension of the coverage_audit slice (product_type, device, geo, ...)."
    }
  }
  label_extractors = {
    "slice_dim" = "EXTRACT(jsonPayload.alert.slice_dim)"
  }
}

resource "google_monitoring_alert_policy" "drift_breach" {
  display_name          = "rpc ${var.env} — per-segment MAE drift > 25% W-o-W"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "any drift breach in the last hour"
    condition_threshold {
      filter          = <<-EOT
        metric.type="logging.googleapis.com/user/${google_logging_metric.drift_breaches.name}"
        resource.type="global"
      EOT
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = <<-EOT
      A per-segment residual MAE moved more than 25% week-over-week.
      The breaching segments (model_version × product_type × device × geo)
      are in `rpc_estimator.drift_breaches_weekly`. Investigate per
      `docs/runbooks/coverage-audit.md §2-§4` if the segment also has a
      coverage drop; otherwise treat as a model-quality signal and verify
      against the residuals_daily chart on the dashboard.
    EOT
  }
}

resource "google_monitoring_alert_policy" "coverage_drop" {
  display_name          = "rpc ${var.env} — coverage dropped > 10pp W-o-W on a slice"
  combiner              = "OR"
  notification_channels = var.alert_notification_channels

  conditions {
    display_name = "any coverage drop in the last hour"
    condition_threshold {
      filter          = <<-EOT
        metric.type="logging.googleapis.com/user/${google_logging_metric.coverage_drops.name}"
        resource.type="cloud_run_revision"
      EOT
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = <<-EOT
      A `coverage_audit` slice lost more than 10 absolute coverage points
      compared to the same day last week. Breaching slices are listed in
      `rpc_estimator.coverage_drops_weekly`. Triage with
      `docs/runbooks/coverage-audit.md` — random vs systematic determines
      whether the alert blocks the next canary promotion.
    EOT
  }
}
