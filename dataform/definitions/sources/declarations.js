// Source table declarations. Named tables created out-of-band by ingestion jobs;
// Dataform does not own them.
declare({ schema: "raw", name: "sales_ledger" });
declare({ schema: "raw", name: "cm360_clicks" });
declare({ schema: "raw", name: "sa360_auctions" });
