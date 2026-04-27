# Runbook — Rotate a Secret Manager secret

Applies to:
- `vertex-endpoint-url-${env}` — Vertex AI predict URL
- `rpc-runtime-config-${env}` — kill switch / bounds / canary config
- `ssgtm-api-key-${env}` — server-side GTM API key

## 1. Add the new version

```bash
PROJECT=msm-rpc
SECRET=vertex-endpoint-url-staging  # or other

# Pipe the new value via stdin so it doesn't land in shell history.
gcloud secrets versions add $SECRET --project=$PROJECT --data-file=- <<EOF
<new value here>
EOF
```

The `terraform` resource for these secrets has `lifecycle { ignore_changes = [secret_data, enabled] }` — Terraform will not overwrite your new version on the next apply.

## 2. Force scoring-api to pick it up

Cloud Run secret env via `value_source.secret_key_ref` is *static at boot* — bumping a secret version does **not** trigger a redeploy. There are two ways to roll the new value into running containers:

```bash
# (a) Trigger a new revision without a code rebuild. The label change is enough.
gcloud run services update scoring-api-staging \
  --project=$PROJECT --region=europe-west2 \
  --update-labels=secret-rotation=$(date +%s)

# (b) Wait for the next CD deploy (tag push). Acceptable only for non-urgent rotations.
```

The runtime-config secret is the exception: `SecretManagerConfig` polls every 15 s (see `services/scoring-api/crates/infrastructure/src/secret_manager_config.rs`), so kill-switch / bounds / canary changes propagate without a revision bump.

## 3. Disable the prior version

After verifying the new version is in use, disable (do not delete) the prior version:

```bash
PRIOR=$(gcloud secrets versions list $SECRET --project=$PROJECT --format='value(name)' --limit=2 | tail -n1)
gcloud secrets versions disable $PRIOR --project=$PROJECT --secret=$SECRET
```

Disabling makes the version immediately unavailable but keeps it for audit. Never run `destroy` — once destroyed a version is unrecoverable.

## 4. Verify

- `gcloud secrets versions list $SECRET` shows the new version `enabled` and the prior `disabled`.
- For `vertex-endpoint-url-*`: `/v1/score` returns model predictions (any 4xx/5xx and you've rotated to a bad URL — re-enable the prior version immediately and investigate).
- For `rpc-runtime-config-*`: read the live secret and confirm the new field appears within ~30 s in scoring-api logs (`runtime_config refresh` line).
