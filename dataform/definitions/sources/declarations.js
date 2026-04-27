// Source table declarations. Tables/views are created by infra/terraform;
// Dataform does not own them. Schema points at the env-suffixed dataset
// (rpc_estimator_staging or rpc_estimator_prod) via the source_dataset var.
const dataset = dataform.projectConfig.vars.source_dataset || "rpc_estimator_staging";
declare({ schema: dataset, name: "sales_ledger" });
declare({ schema: dataset, name: "cm360_clicks" });
declare({ schema: dataset, name: "sa360_auctions" });
declare({ schema: dataset, name: "rpc_predictions" });
declare({ schema: dataset, name: "rpc_training_rows" });
