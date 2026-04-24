#!/usr/bin/env bash
# One-shot bootstrap for a fresh GCP staging environment.
#
# Prereqs on the operator's machine:
#   - gcloud authenticated as a user with Owner on $PROJECT
#   - gh authenticated against the asmeyatsky-work/msm repo
#   - terraform ≥1.8.0
#
# What this does:
#   1. Creates an Artifact Registry repo for container images.
#   2. Creates a GCS bucket for terraform state.
#   3. Runs terraform apply to create WIF + data-plane resources.
#   4. Sets the four GH Actions secrets from TF outputs.
#
# After this script succeeds, the first `git push --tags` (or manual
# workflow_dispatch) triggers cd.yml end-to-end.
set -euo pipefail

: "${PROJECT:?set PROJECT=<gcp-project-id>}"
: "${REGION:=us-central1}"
: "${ENV:=staging}"

echo "==> 0/4 Enable required APIs"
gcloud --project="$PROJECT" services enable \
  iam.googleapis.com iamcredentials.googleapis.com \
  run.googleapis.com cloudresourcemanager.googleapis.com \
  artifactregistry.googleapis.com bigquery.googleapis.com \
  pubsub.googleapis.com secretmanager.googleapis.com \
  cloudbuild.googleapis.com cloudscheduler.googleapis.com \
  aiplatform.googleapis.com storage.googleapis.com \
  serviceusage.googleapis.com sts.googleapis.com --quiet

echo "==> 1/4 Artifact Registry"
gcloud --project="$PROJECT" artifacts repositories create rpc-estimator \
  --repository-format=docker --location="$REGION" \
  --description="Predictive RPC Estimator images" 2>/dev/null || \
  echo "    (already exists)"

echo "==> 2/4 Terraform state bucket"
TF_STATE_BUCKET="${PROJECT}-rpc-tf-state-${ENV}"
gcloud storage buckets create "gs://${TF_STATE_BUCKET}" \
  --project="$PROJECT" --location="$REGION" --uniform-bucket-level-access 2>/dev/null || \
  echo "    (already exists)"

echo "==> 3/4 terraform apply"
cd "$(dirname "$0")/../infra/terraform"
terraform init -reconfigure -backend-config="bucket=${TF_STATE_BUCKET}"

# First apply uses placeholder images so the WIF + data plane + secret land
# before any container exists. cd.yml replaces these with real SHAs later.
terraform apply -auto-approve -lock-timeout=5m \
  -var="project_id=${PROJECT}" \
  -var="region=${REGION}" \
  -var="env=${ENV}" \
  -var="image_scoring_api=gcr.io/cloudrun/hello" \
  -var="image_reconciliation=gcr.io/cloudrun/hello" \
  -var="image_activation=gcr.io/cloudrun/hello" \
  -var="image_breaker=gcr.io/cloudrun/hello" \
  -var="image_ml_pipeline=gcr.io/cloudrun/hello"

WIF=$(terraform output -raw wif_provider_resource)
CI_SA=$(terraform output -raw ci_service_account)

echo "==> 4/4 GitHub Actions secrets"
gh secret set GCP_PROJECT          -b "$PROJECT"
gh secret set GCP_WIF_PROVIDER     -b "$WIF"
gh secret set GCP_CI_SA            -b "$CI_SA"
gh secret set TF_STATE_BUCKET      -b "$TF_STATE_BUCKET"

echo ""
echo "✓ bootstrap complete. Next:"
echo "   git tag -a v0.1.0 -m 'first deploy' && git push --tags"
echo "   → cd.yml will build images, terraform apply with real SHAs,"
echo "     and run ops/smoke.sh against the deployed scoring-api."
