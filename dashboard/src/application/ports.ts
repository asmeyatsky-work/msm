// Ports. Layer: application (§2). Imports only `domain`.
import type { CoverageSlice, ReconciliationRow } from "../domain/reconciliation";

export interface ReconciliationGateway {
  fetchWindow(
    startMs: number,
    endMs: number,
    productType?: string,
  ): Promise<ReconciliationRow[]>;
  fetchCoverage(): Promise<CoverageSlice[]>;
}
