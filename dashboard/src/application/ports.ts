// Ports. Layer: application (§2). Imports only `domain`.
import type { ReconciliationRow } from "../domain/reconciliation";

export interface ReconciliationGateway {
  fetchWindow(startMs: number, endMs: number): Promise<ReconciliationRow[]>;
}
