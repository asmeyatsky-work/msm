// Use case — pure orchestration. §5 Application floor: mock ports only in tests.
import type { ReconciliationRow } from "../domain/reconciliation";
import { rowIsComplete } from "../domain/reconciliation";
import type { ReconciliationGateway } from "./ports";

export class LoadReconciliation {
  constructor(private readonly gateway: ReconciliationGateway) {}

  async execute(startMs: number, endMs: number, nowMs: number): Promise<{
    completed: ReconciliationRow[];
    pending: ReconciliationRow[];
  }> {
    const rows = await this.gateway.fetchWindow(startMs, endMs);
    const completed: ReconciliationRow[] = [];
    const pending: ReconciliationRow[] = [];
    for (const r of rows) (rowIsComplete(r, nowMs) ? completed : pending).push(r);
    return { completed, pending };
  }
}
