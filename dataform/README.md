# Dataform — feature pipelines

Produces the training inputs consumed by `services/ml-pipeline` and the
reconciliation view consumed by `services/reconciliation`.

Graph:

```
sources.sales_ledger ─┐
sources.cm360_clicks ─┼─► staging.click_revenue  ─► training.rpc_training_rows
sources.sa360_auctions ┘                           └─► staging.rolling_rpc
```

All datasets respect the PRD §3.2 configurable conversion window via the
`conversion_window_days` variable (default 30).
