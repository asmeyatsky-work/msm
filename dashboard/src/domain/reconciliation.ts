// Dashboard domain — pure types for reconciliation of predicted vs. realized revenue.
// Layer: domain (§2). No framework imports. Schema: PRD V2 (Credit Cards) §4.2.

export type ClickId = string & { readonly __brand: "ClickId" };

export interface ReconciliationRow {
  readonly clickId: ClickId;
  readonly predictedRpc: number;
  readonly realizedRpc: number;
  readonly source: "MODEL" | "FALLBACK_TCPA" | "FALLBACK_DATA_LAYER" | "KILL_SWITCH";
  readonly windowEndsAtMs: number;
  readonly verticalId: string;
  readonly productType: string;
  readonly modelVersion: string;
}

export function residual(row: ReconciliationRow): number {
  return row.realizedRpc - row.predictedRpc;
}

export function rowIsComplete(row: ReconciliationRow, nowMs: number): boolean {
  return nowMs >= row.windowEndsAtMs;
}

// PRD V2 §4.3 — coverage slice surfaced by /coverage.
export interface CoverageSlice {
  readonly sliceDim: string;
  readonly sliceValue: string;
  readonly clicks: number;
  readonly coveredClicks: number;
  readonly coverageRate: number;
}
