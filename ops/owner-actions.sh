#!/usr/bin/env bash
# Owner-ADC orchestration. Runs the manual steps that Claude can't do from
# its sandboxed shell: terraform applies against live GCP, model retrain,
# load profile, prod-project bootstrap, notification-channel wiring.
#
# Prereqs on the operator's machine:
#   - gcloud authenticated as project Owner (`gcloud auth login` + ADC)
#   - gh authenticated against asmeyatsky-work/msm
#   - terraform ≥ 1.8.0
#   - python3, jq, oha (for load-test only)
#
# Usage:
#   ops/owner-actions.sh apply-staging       # tf apply against staging
#   ops/owner-actions.sh load-test           # ops/perf/staging-load.sh
#   ops/owner-actions.sh deploy-model        # ops/deploy_real_model.py
#   ops/owner-actions.sh wire-notifications  # create email notif channel
#   ops/owner-actions.sh bootstrap-prod      # one-time prod project bootstrap
#   ops/owner-actions.sh all-staging         # 1+2+3 in order
#
# Each subcommand is idempotent where it can be; destructive prod actions
# require an explicit yes/no confirmation.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_STAGING="${PROJECT_STAGING:-msm-rpc}"
REGION="${REGION:-europe-west2}"
TF_STATE_STAGING="${TF_STATE_STAGING:-${PROJECT_STAGING}-rpc-tf-state-staging}"

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*" >&2; }
step()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

require() {
  local missing=0
  for cmd in "$@"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      red "missing required tool: $cmd"
      missing=1
    fi
  done
  (( missing == 0 )) || exit 1
}

confirm() {
  local prompt="$1"
  read -r -p "$prompt [y/N] " ans
  case "$ans" in y|Y|yes|YES) return 0 ;; *) red "aborted"; exit 2 ;; esac
}

ensure_adc() {
  local proj="$1"
  local adc_file="${HOME}/.config/gcloud/application_default_credentials.json"

  if [[ ! -f "$adc_file" ]]; then
    red "ADC not set. Run:"
    red "   gcloud auth application-default login"
    red "   gcloud auth application-default set-quota-project $proj"
    exit 1
  fi
  if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    red "ADC token cannot be minted. Try re-authing:"
    red "   gcloud auth application-default login"
    exit 1
  fi
  # Quota project is best-effort — print-access-token doesn't honour
  # --quota-project on every gcloud version. Warn but don't block.
  if command -v jq >/dev/null 2>&1; then
    local current
    current=$(jq -r '.quota_project_id // empty' "$adc_file" 2>/dev/null || true)
    if [[ -n "$current" && "$current" != "$proj" ]]; then
      red "ADC quota project is '$current', expected '$proj'. Fixing:"
      gcloud auth application-default set-quota-project "$proj"
    fi
  fi
}

# ---------- 1. terraform apply staging ---------------------------------------
cmd_apply_staging() {
  require gcloud terraform jq
  ensure_adc "$PROJECT_STAGING"

  step "1/1  terraform apply (staging)"

  # Pull the latest images that CD has already pushed; fall back to the
  # cloud-run hello placeholder for any service whose image is missing
  # (e.g. mock-vertex was retired).
  local repo="${REGION}-docker.pkg.dev/${PROJECT_STAGING}/rpc-estimator"
  latest() {
    gcloud artifacts docker images list "${repo}/$1" \
      --project="$PROJECT_STAGING" \
      --format='value(IMAGE,DIGEST)' --sort-by='~CREATE_TIME' --limit=1 \
      | head -n1 | awk '{print $1"@"$2}'
  }

  local img_scoring img_recon img_act img_break img_ml
  img_scoring=$(latest scoring-api      || true)
  img_recon=$(latest reconciliation     || true)
  img_act=$(latest activation           || true)
  img_break=$(latest breaker-automation || true)
  img_ml=$(latest ml-pipeline           || true)
  : "${img_scoring:=gcr.io/cloudrun/hello}"
  : "${img_recon:=gcr.io/cloudrun/hello}"
  : "${img_act:=gcr.io/cloudrun/hello}"
  : "${img_break:=gcr.io/cloudrun/hello}"
  : "${img_ml:=gcr.io/cloudrun/hello}"

  local token
  token=$(gcloud auth application-default print-access-token \
            --scopes="https://www.googleapis.com/auth/cloud-platform")

  cd "${ROOT}/infra/terraform"
  terraform init -reconfigure \
    -backend-config="bucket=${TF_STATE_STAGING}" \
    -backend-config="access_token=${token}"

  terraform apply -auto-approve -lock-timeout=5m \
    -var-file=envs/staging.tfvars \
    -var="project_id=${PROJECT_STAGING}" \
    -var="image_scoring_api=${img_scoring}" \
    -var="image_reconciliation=${img_recon}" \
    -var="image_activation=${img_act}" \
    -var="image_breaker=${img_break}" \
    -var="image_ml_pipeline=${img_ml}"

  green "✓ staging apply complete"
  terraform output -raw scoring_api_url
  echo ""
}

# ---------- 2. load profile against staging ----------------------------------
cmd_load_test() {
  require oha gcloud jq curl
  step "2/?  staging load profile"

  local url
  if url=$(cd "${ROOT}/infra/terraform" && terraform output -raw scoring_api_url 2>/dev/null); then
    export SCORING_API_URL="$url"
  fi
  : "${SCORING_API_URL:?SCORING_API_URL not set and terraform state has no scoring_api_url; export it manually}"

  echo "    target: $SCORING_API_URL"
  bash "${ROOT}/ops/perf/staging-load.sh" both
  green "✓ load profile complete; results under ops/perf/"
}

# ---------- 3. deploy real model with explanationSpec ------------------------
cmd_deploy_model() {
  require gcloud python3
  ensure_adc "$PROJECT_STAGING"
  step "3/?  retrain + register rpc-estimator (with explanationSpec)"

  if [[ "$(uname -s)" == "Darwin" ]] && ! brew list libomp >/dev/null 2>&1; then
    bold "    macOS: installing libomp (xgboost runtime dep)"
    brew install libomp
  fi

  # PEP 668: Homebrew Python is externally-managed. Use a project-local venv
  # so we don't have to --break-system-packages or pollute the user site.
  local venv="${ROOT}/.venv-deploy-model"
  if [[ ! -d "$venv" ]]; then
    bold "    creating venv at $venv"
    python3 -m venv "$venv"
  fi
  # shellcheck disable=SC1091
  source "$venv/bin/activate"

  if ! python3 -c 'import xgboost, sklearn, google.cloud.aiplatform' 2>/dev/null; then
    bold "    installing python deps into venv"
    python3 -m pip install --quiet --upgrade pip
    python3 -m pip install --quiet \
      xgboost scikit-learn pandas db-dtypes \
      google-cloud-bigquery google-cloud-aiplatform \
      google-cloud-storage google-cloud-secret-manager
  fi

  python3 "${ROOT}/ops/deploy_real_model.py"
  deactivate
  green "✓ rpc-estimator registered + endpoint updated"
}

# ---------- 4. wire a notification channel for monitoring alerts -------------
cmd_wire_notifications() {
  require gcloud jq
  ensure_adc "$PROJECT_STAGING"
  step "4/?  Cloud Monitoring notification channel"

  local email
  read -r -p "    email address for alerts: " email
  [[ -n "$email" ]] || { red "no email — aborted"; exit 2; }

  local existing
  existing=$(gcloud alpha monitoring channels list \
    --project="$PROJECT_STAGING" \
    --filter="type=email AND labels.email_address=${email}" \
    --format='value(name)' | head -n1 || true)

  local channel_id="$existing"
  if [[ -z "$channel_id" ]]; then
    channel_id=$(gcloud alpha monitoring channels create \
      --project="$PROJECT_STAGING" \
      --display-name="msm alerts (${email})" \
      --type=email \
      --channel-labels="email_address=${email}" \
      --format='value(name)')
    green "    created channel: $channel_id"
  else
    bold "    re-using existing channel: $channel_id"
  fi

  # Persist into the per-env tfvars so future tf applies wire it in.
  local tfvars="${ROOT}/infra/terraform/envs/staging.tfvars"
  if grep -q '^alert_notification_channels' "$tfvars"; then
    # Replace the line.
    awk -v c="$channel_id" '
      /^alert_notification_channels[[:space:]]*=/ {
        print "alert_notification_channels = [\"" c "\"]"; next
      } { print }
    ' "$tfvars" > "${tfvars}.tmp" && mv "${tfvars}.tmp" "$tfvars"
  else
    printf '\nalert_notification_channels = ["%s"]\n' "$channel_id" >> "$tfvars"
  fi

  green "✓ wrote channel into envs/staging.tfvars; commit + re-run apply-staging to apply"
}

# ---------- 5. one-time prod project bootstrap -------------------------------
cmd_bootstrap_prod() {
  require gcloud gh terraform jq
  step "5/?  prod-project bootstrap"

  bold "Reads docs/runbooks/rollback-plan.md and infra/terraform/envs/README.md before continuing."
  read -r -p "    prod GCP project ID: "      PROJECT_PROD
  : "${PROJECT_PROD:?project required}"

  ensure_adc "$PROJECT_PROD"

  local current
  current=$(gcloud config get-value project 2>/dev/null || true)
  if [[ "$current" != "$PROJECT_PROD" ]]; then
    bold "    setting active project to $PROJECT_PROD"
    gcloud config set project "$PROJECT_PROD"
  fi

  bold "About to:"
  echo "  • enable APIs on $PROJECT_PROD"
  echo "  • create gs://${PROJECT_PROD}-rpc-tf-state-prod"
  echo "  • create artifact registry rpc-estimator in $REGION"
  echo "  • run terraform apply against $PROJECT_PROD with envs/prod.tfvars"
  echo "  • set GH variable GCP_PROJECT_PROD and secrets GCP_WIF_PROVIDER_PROD,"
  echo "    GCP_CI_SA_PROD, TF_STATE_BUCKET_PROD"
  echo "  • DOES NOT flip vars.DEPLOY_PROD — that's a separate manual step"
  confirm "Proceed?"

  step "5a/  enable APIs"
  gcloud --project="$PROJECT_PROD" services enable \
    iam.googleapis.com iamcredentials.googleapis.com \
    run.googleapis.com cloudresourcemanager.googleapis.com \
    artifactregistry.googleapis.com bigquery.googleapis.com \
    pubsub.googleapis.com secretmanager.googleapis.com \
    cloudbuild.googleapis.com cloudscheduler.googleapis.com \
    aiplatform.googleapis.com storage.googleapis.com \
    monitoring.googleapis.com logging.googleapis.com \
    serviceusage.googleapis.com sts.googleapis.com --quiet

  step "5b/  artifact registry"
  gcloud --project="$PROJECT_PROD" artifacts repositories create rpc-estimator \
    --repository-format=docker --location="$REGION" \
    --description="Predictive RPC Estimator images (prod)" 2>/dev/null \
    || bold "    (already exists)"

  step "5c/  terraform state bucket"
  local tf_state_prod="${PROJECT_PROD}-rpc-tf-state-prod"
  gcloud storage buckets create "gs://${tf_state_prod}" \
    --project="$PROJECT_PROD" --location="$REGION" \
    --uniform-bucket-level-access 2>/dev/null \
    || bold "    (already exists)"
  gcloud storage buckets update "gs://${tf_state_prod}" \
    --project="$PROJECT_PROD" --versioning >/dev/null

  step "5d/  terraform apply (prod, placeholder images)"
  local token
  token=$(gcloud auth application-default print-access-token \
            --scopes="https://www.googleapis.com/auth/cloud-platform")
  cd "${ROOT}/infra/terraform"
  terraform init -reconfigure \
    -backend-config="bucket=${tf_state_prod}" \
    -backend-config="access_token=${token}"
  terraform apply -auto-approve -lock-timeout=10m \
    -var-file=envs/prod.tfvars \
    -var="project_id=${PROJECT_PROD}" \
    -var="image_scoring_api=gcr.io/cloudrun/hello" \
    -var="image_reconciliation=gcr.io/cloudrun/hello" \
    -var="image_activation=gcr.io/cloudrun/hello" \
    -var="image_breaker=gcr.io/cloudrun/hello" \
    -var="image_ml_pipeline=gcr.io/cloudrun/hello"

  local wif ci_sa
  wif=$(terraform output -raw wif_provider_resource)
  ci_sa=$(terraform output -raw ci_service_account)

  step "5e/  GitHub secrets/variables (prod)"
  gh variable set GCP_PROJECT_PROD --body "$PROJECT_PROD"
  gh secret   set GCP_WIF_PROVIDER_PROD --body "$wif"
  gh secret   set GCP_CI_SA_PROD --body "$ci_sa"
  gh secret   set TF_STATE_BUCKET_PROD --body "$tf_state_prod"

  green "✓ prod project bootstrapped."
  cat <<EOF

Next steps (manual):
  1. Re-run \`ops/deploy_real_model.py\` against $PROJECT_PROD to register
     a real Vertex model + write vertex-endpoint-url-prod secret.
  2. Wire a prod notification channel: \`PROJECT_STAGING=$PROJECT_PROD ops/owner-actions.sh wire-notifications\`
     (and adjust the resulting tfvars: it writes to envs/staging.tfvars; copy the line into prod.tfvars).
  3. Set \`vars.DEPLOY_PROD=true\` on the repo: \`gh variable set DEPLOY_PROD --body true\`
  4. Tag and push: \`git tag v0.x.0 && git push origin v0.x.0\`
EOF
}

# ---------- composite --------------------------------------------------------
cmd_all_staging() {
  cmd_apply_staging
  cmd_deploy_model
  cmd_load_test
}

usage() {
  sed -n '2,25p' "$0"
}

case "${1:-}" in
  apply-staging)      cmd_apply_staging ;;
  load-test)          cmd_load_test ;;
  deploy-model)       cmd_deploy_model ;;
  wire-notifications) cmd_wire_notifications ;;
  bootstrap-prod)     cmd_bootstrap_prod ;;
  all-staging)        cmd_all_staging ;;
  -h|--help|"")       usage ;;
  *) red "unknown subcommand: $1"; usage; exit 2 ;;
esac
