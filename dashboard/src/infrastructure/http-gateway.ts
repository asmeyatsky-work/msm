// HTTP adapter over Looker/BigQuery reconciliation endpoint (§4: Zod validation).
import { z } from "zod";
import type { ReconciliationGateway } from "../application/ports";
import type { ClickId, CoverageSlice, ReconciliationRow } from "../domain/reconciliation";

const rowSchema = z.object({
  click_id: z.string().min(1),
  predicted_rpc: z.number().nonnegative(),
  realized_rpc: z.number().nonnegative(),
  source: z.enum(["MODEL", "FALLBACK_TCPA", "FALLBACK_DATA_LAYER", "KILL_SWITCH"]),
  window_ends_at_ms: z.number().int().nonnegative(),
  // PRD V2 §4.2 — defaulted so the dashboard keeps working against an
  // older reconciliation service deployment that hasn't picked up the new
  // columns yet.
  vertical_id: z.string().default("credit_cards"),
  product_type: z.string().default(""),
  model_version: z.string().default(""),
});

const coverageSchema = z.object({
  slice_dim: z.string(),
  slice_value: z.string(),
  clicks: z.number().int().nonnegative(),
  covered_clicks: z.number().int().nonnegative(),
  coverage_rate: z.number(),
});

export class HttpReconciliationGateway implements ReconciliationGateway {
  constructor(private readonly baseUrl: string, private readonly timeoutMs = 15000) {}

  async fetchWindow(
    startMs: number,
    endMs: number,
    productType?: string,
  ): Promise<ReconciliationRow[]> {
    // §3.2: every external call has an explicit timeout.
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), this.timeoutMs);
    try {
      const qs = new URLSearchParams({
        start: String(startMs),
        end: String(endMs),
      });
      if (productType) qs.set("product_type", productType);
      const resp = await fetch(`${this.baseUrl}/reconciliation?${qs}`, {
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
        verticalId: r.vertical_id,
        productType: r.product_type,
        modelVersion: r.model_version,
      }));
    } finally {
      clearTimeout(t);
    }
  }

  async fetchCoverage(): Promise<CoverageSlice[]> {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), this.timeoutMs);
    try {
      const resp = await fetch(`${this.baseUrl}/coverage`, { signal: ctl.signal });
      if (!resp.ok) throw new Error(`status ${resp.status}`);
      const raw = await resp.json();
      return z.array(coverageSchema).parse(raw).map((c) => ({
        sliceDim: c.slice_dim,
        sliceValue: c.slice_value,
        clicks: c.clicks,
        coveredClicks: c.covered_clicks,
        coverageRate: c.coverage_rate,
      }));
    } finally {
      clearTimeout(t);
    }
  }
}
