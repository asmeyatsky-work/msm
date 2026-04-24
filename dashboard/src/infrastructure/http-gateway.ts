// HTTP adapter over Looker/BigQuery reconciliation endpoint (§4: Zod validation).
import { z } from "zod";
import type { ReconciliationGateway } from "../application/ports";
import type { ClickId, ReconciliationRow } from "../domain/reconciliation";

const rowSchema = z.object({
  click_id: z.string().min(1),
  predicted_rpc: z.number().nonnegative(),
  realized_rpc: z.number().nonnegative(),
  source: z.enum(["MODEL", "FALLBACK_TCPA", "FALLBACK_DATA_LAYER", "KILL_SWITCH"]),
  window_ends_at_ms: z.number().int().nonnegative(),
});

export class HttpReconciliationGateway implements ReconciliationGateway {
  constructor(private readonly baseUrl: string, private readonly timeoutMs = 3000) {}

  async fetchWindow(startMs: number, endMs: number): Promise<ReconciliationRow[]> {
    // §3.2: every external call has an explicit timeout.
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), this.timeoutMs);
    try {
      const resp = await fetch(`${this.baseUrl}/reconciliation?start=${startMs}&end=${endMs}`, {
        signal: ctl.signal,
      });
      if (!resp.ok) throw new Error(`status ${resp.status}`);
      const raw = await resp.json();
      return z.array(rowSchema).parse(raw).map((r) => ({
        clickId: r.click_id as ClickId,
        predictedRpc: r.predicted_rpc,
        realizedRpc: r.realized_rpc,
        source: r.source,
        windowEndsAtMs: r.window_ends_at_ms,
      }));
    } finally {
      clearTimeout(t);
    }
  }
}
