// Dashboard domain — pure types for reconciliation of predicted vs. realized revenue.
// Layer: domain (§2). No framework imports.

export type ClickId = string & { readonly __brand: "ClickId" };

export interface ReconciliationRow {
  readonly clickId: ClickId;
  readonly predictedRpc: number;
  readonly realizedRpc: number;
  readonly source: "MODEL" | "FALLBACK_TCPA" | "FALLBACK_DATA_LAYER" | "KILL_SWITCH";
  readonly windowEndsAtMs: number;
}

export function residual(row: ReconciliationRow): number {
  return row.realizedRpc - row.predictedRpc;
}

export function rowIsComplete(row: ReconciliationRow, nowMs: number): boolean {
  return nowMs >= row.windowEndsAtMs;
}
