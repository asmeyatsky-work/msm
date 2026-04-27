# Environment workspaces

The `infra/terraform` module is **shared between staging and prod** — each env gets its own state bucket, WIF pool, project, and tfvars file.

## Layout

```
infra/terraform/
├── envs/
│   ├── staging.tfvars   ← anomaly 0.50, min=1; relaxed for synthetic data
│   └── prod.tfvars      ← anomaly 0.03, min=2; PRD §5 strict
├── variables_runtime.tf ← all envs see the same variables
└── …                    ← rest of the module is env-agnostic
```

## Apply

```bash
# Auth (assumes ADC for the env's CI SA)
TOKEN=$(gcloud auth application-default print-access-token \
          --scopes="https://www.googleapis.com/auth/cloud-platform")

# Pick env
ENV=prod   # or staging
BUCKET=msm-rpc-rpc-tf-state-${ENV}

cd infra/terraform
terraform init -reconfigure \
  -backend-config="bucket=${BUCKET}" \
  -backend-config="access_token=${TOKEN}"

terraform apply -var-file=envs/${ENV}.tfvars \
  -var="project_id=${GCP_PROJECT}" \
  -var="image_scoring_api=…" \
  -var="image_reconciliation=…" \
  -var="image_activation=…" \
  -var="image_breaker=…" \
  -var="image_ml_pipeline=…" \
  -var="image_mock_vertex="
```

CD does this automatically — see `.github/workflows/cd.yml` (`deploy-staging` and `deploy-prod` jobs).

## Bootstrapping a fresh prod project

This is a one-time procedure that requires a human with project Owner. After it runs, CD takes over.

1. **Create or pick a GCP project** for prod. Note the numeric project number.
2. **Create the Terraform state bucket** in that project:
   ```bash
   gcloud storage buckets create gs://${PROJECT}-rpc-tf-state-prod \
     --project=${PROJECT} \
     --location=europe-west2 \
     --uniform-bucket-level-access
   gcloud storage buckets update gs://${PROJECT}-rpc-tf-state-prod \
     --versioning
   ```
3. **Run `ops/bootstrap.sh`** with Owner ADC to seed the WIF pool, CI SA, and grant the bootstrap roles. The script is idempotent.
4. **Wire GitHub Actions secrets/vars** in the repo:
   - `vars.GCP_PROJECT_PROD` = the prod project ID
   - `secrets.GCP_WIF_PROVIDER_PROD` = full provider resource name (printed by tf apply once the WIF pool exists)
   - `secrets.GCP_CI_SA_PROD` = `ci-deployer-prod@${PROJECT}.iam.gserviceaccount.com`
   - `secrets.TF_STATE_BUCKET_PROD` = `${PROJECT}-rpc-tf-state-prod`
5. **Set `vars.DEPLOY_PROD=true`** to enable the prod CD job.
6. **First-tag deploy**: `git tag v0.x.0 && git push origin v0.x.0`. Watch `cd.yml` — staging deploys first, then prod gates on the `prod` GitHub environment for approval.
7. **Re-run `ops/deploy_real_model.py`** against the prod project once tf is in place — it registers the model + creates the Vertex endpoint + writes `vertex-endpoint-url-prod` secret.

## Drift check

`terraform plan -var-file=envs/${ENV}.tfvars …` against an env should be empty. Anything non-empty is a configuration drift; resolve before merging Phase 3 work.
