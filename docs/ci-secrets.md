# GitHub Actions secrets

One-time setup to make `cd.yml` actually deploy. All values come from
Terraform outputs after `terraform apply` in `infra/terraform/` against a
bootstrap GCP project.

| Secret                         | Source / value                                                                 |
|--------------------------------|--------------------------------------------------------------------------------|
| `GCP_PROJECT`                  | Project ID for staging (e.g. `msm-rpc-staging`)                                |
| `GCP_WIF_PROVIDER`             | Terraform output `wif_provider_resource` from `wif.tf`                         |
| `GCP_CI_SA`                    | Terraform output `ci_service_account` (staging)                                |
| `TF_STATE_BUCKET`              | GCS bucket name holding the terraform state (bootstrap-time; not managed by TF)|
| `SCORING_API_URL_STAGING`      | Cloud Run URL of `scoring-api-staging` — fills in post-first-deploy            |
| `GCP_PROJECT_PROD`             | Same for prod                                                                  |
| `GCP_WIF_PROVIDER_PROD`        | Same for prod                                                                  |
| `GCP_CI_SA_PROD`               | Same for prod                                                                  |
| `TF_STATE_BUCKET_PROD`         | Same for prod                                                                  |

## Bootstrap

```bash
# 1) Create GCS bucket for TF state (one-off; outside TF).
gsutil mb -p $BOOTSTRAP_PROJECT -l us-central1 gs://msm-rpc-tf-state-staging

# 2) Apply WIF + initial infra.
cd infra/terraform
terraform init -backend-config="bucket=msm-rpc-tf-state-staging"
terraform apply -var project_id=$GCP_PROJECT -var env=staging \
  -var image_scoring_api=placeholder \
  -var image_reconciliation=placeholder \
  -var image_activation=placeholder \
  -var image_breaker=placeholder \
  -var image_ml_pipeline=placeholder

# 3) Copy outputs into GH Actions:
terraform output wif_provider_resource    # → GCP_WIF_PROVIDER
terraform output ci_service_account       # → GCP_CI_SA
```

Set via `gh`:

```bash
gh secret set GCP_PROJECT          -b "$PROJECT"
gh secret set GCP_WIF_PROVIDER     -b "$(terraform output -raw wif_provider_resource)"
gh secret set GCP_CI_SA            -b "$(terraform output -raw ci_service_account)"
gh secret set TF_STATE_BUCKET      -b "msm-rpc-tf-state-staging"
```

## Environments (prod gate)

The `deploy-prod` job in `cd.yml` uses GitHub Environments for manual approval.
Create an environment called `prod` under Settings → Environments and add
required reviewers.
