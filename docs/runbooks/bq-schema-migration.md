# Runbook — BigQuery schema migration

Applies to:
- `sales_ledger` (data-contract feed)
- `cm360_clicks` (typed view) and `cm360_clicks_raw` (Pub/Sub landing)
- `rpc_predictions` (typed view) and `rpc_predictions_raw`
- Dataform-built monitoring tables (`feature_baseline`, `psi_daily`, `residuals_daily`)

## 0. Hard rules (data-contract §5)

- **Breaking change** = renaming a column, dropping a column, narrowing a type, changing the meaning of a value.
- Breaking changes **do not** mutate live tables — open a new dataset (`rpc_estimator_${env}_v2`) and migrate in parallel.
- **Additive change** = appending a NULLABLE column. Ship via Terraform `schema = jsonencode([...])` update; no data move required.

## 1. Additive change (NULLABLE column)

1. Edit the `schema = jsonencode([...])` block in `infra/terraform/main.tf`. Mode must be `"NULLABLE"`.
2. Update the typed view in the same file (`google_bigquery_table.*_view`) to expose the new column.
3. `terraform plan -var-file=envs/staging.tfvars …` — confirm only the table + view change.
4. `terraform apply` (CD on tag push, or manually). BigQuery accepts the column add online; no downtime.
5. Update `docs/data-contract.md` and bump its sign-off block.

## 2. Breaking change

Treat as a parallel migration, not an in-place change.

1. Provision the new dataset (`rpc_estimator_${env}_v2`) in Terraform with the new schema. Same module, distinct dataset_id; the existing `var.env` does not need to change.
2. Backfill historical data into the new dataset:
   ```bash
   bq cp -a --project_id=msm-rpc \
     msm-rpc:rpc_estimator_staging.sales_ledger \
     msm-rpc:rpc_estimator_staging_v2.sales_ledger
   # Then run the migration SQL (CASTs / column rewrites) in v2.
   ```
3. Tee live writes — for Pub/Sub-fed tables, add a second BQ subscription on the same topic landing in `_v2`.
4. Cut readers (scoring-api, Dataform, BI) over to the new dataset behind a feature flag (`BQ_DATASET` env). Keep the old dataset live for 7 days as a rollback.
5. After 7 days clean, drop the old dataset (Terraform `terraform state rm` + console delete; **do not** rely on Terraform destroy — BigQuery datasets with `deletion_protection = false` will silently take their data with them).

## 3. Verification

- Schema in BigQuery console matches the Terraform definition exactly (columns + modes + types).
- Existing queries against the typed views still parse and return rows.
- Dataform `dataform run` succeeds.
- `dataform test` (assertions defined alongside the SQLX) passes.

## 4. Common gotchas

- Pub/Sub→BQ subscription with `drop_unknown_fields = true` silently drops messages with the new field until the destination table has it. Update the table schema **before** publishers start sending the new field.
- Adding a REQUIRED column requires backfill first (BigQuery rejects rows with NULL for REQUIRED). Always add as NULLABLE and tighten later.
- Views fail `terraform apply` with "no schema" if the underlying table column was just added — re-applying once usually fixes it; if not, apply the table change first, then the view.
