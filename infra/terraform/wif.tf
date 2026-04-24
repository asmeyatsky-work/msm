# Workload Identity Federation for GitHub Actions CD.
# §4: no long-lived service account keys; GH Actions assumes an SA via WIF.
#
# One-time setup is split into two layers:
#
#   1. The pool + provider + SA bindings defined here (terraform apply from
#      a bootstrap project with owner credentials).
#   2. The matching GitHub Actions secrets listed in docs/ci-secrets.md.
#
# Once both sides are in place, cd.yml can run `terraform apply` on every
# tag / manual dispatch without any key material.

variable "github_org" {
  type    = string
  default = "asmeyatsky-work"
}
variable "github_repo" {
  type    = string
  default = "msm"
}

resource "google_iam_workload_identity_pool" "gh" {
  workload_identity_pool_id = "github-${var.env}"
  display_name              = "GitHub Actions (${var.env})"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.gh.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  # Restrict to commits from this repo. Any other repo or fork trying to
  # assume the role gets rejected at the token-exchange step.
  attribute_condition = "assertion.repository == \"${var.github_org}/${var.github_repo}\""

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "ci" {
  account_id   = "ci-deployer-${var.env}"
  display_name = "CI deployer (GH Actions via WIF)"
}

resource "google_service_account_iam_binding" "ci_wif" {
  service_account_id = google_service_account.ci.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.gh.name}/attribute.repository/${var.github_org}/${var.github_repo}",
  ]
}

# CI needs Cloud Run deployer, Artifact Registry writer, Secret Manager
# accessor (read-only to deploy-time config), and BigQuery dataset admin
# (for dataform + table lifecycle). Scoped to project only.
resource "google_project_iam_member" "ci_run" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

resource "google_project_iam_member" "ci_ar" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

resource "google_project_iam_member" "ci_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

resource "google_project_iam_member" "ci_tf_state" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.ci.email}"
}

output "wif_provider_resource" {
  description = "Value for the GCP_WIF_PROVIDER GitHub Actions secret."
  value       = "projects/${data.google_project.this.number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.gh.workload_identity_pool_id}/providers/${google_iam_workload_identity_pool_provider.github.workload_identity_pool_provider_id}"
}

output "ci_service_account" {
  description = "Value for the GCP_CI_SA GitHub Actions secret."
  value       = google_service_account.ci.email
}

data "google_project" "this" {
  project_id = var.project_id
}
