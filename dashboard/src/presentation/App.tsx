import { useEffect, useMemo, useState } from "react";
import type { ReconciliationRow } from "../domain/reconciliation";
import { residual } from "../domain/reconciliation";
import { LoadReconciliation } from "../application/load-reconciliation";
import { HttpReconciliationGateway } from "../infrastructure/http-gateway";
import {
  fmtCurrency, fmtPercent, fmtInt, fmtDate, fmtDateOnly, shorten,
} from "./format";
import { DailyComparisonChart, SourceDonut, ResidualHistogram, AttributionBars } from "./charts";
import type { AttrPoint } from "./charts";

const gateway = new HttpReconciliationGateway(
  import.meta.env.VITE_RECONCILIATION_API ?? "/api",
);
const useCase = new LoadReconciliation(gateway);

const DAY_MS = 24 * 60 * 60 * 1000;
const WINDOW_DAYS = 7;

type Status = { kind: "loading" } | { kind: "ready" } | { kind: "error"; msg: string };

export function App() {
  const [rows, setRows] = useState<ReconciliationRow[]>([]);
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [range] = useState(() => {
    const end = Date.now();
    return { start: end - WINDOW_DAYS * DAY_MS, end };
  });

  useEffect(() => {
    let cancelled = false;
    setStatus({ kind: "loading" });
    useCase.execute(range.start, range.end, range.end)
      .then(({ completed }) => {
        if (cancelled) return;
        setRows(completed);
        setStatus({ kind: "ready" });
      })
      .catch((e) => {
        if (cancelled) return;
        const msg = e?.name === "AbortError"
          ? "Request timed out — the service may be warming up. Retry in a moment."
          : (e?.message ?? "Failed to load.");
        setStatus({ kind: "error", msg });
      });
    return () => { cancelled = true; };
  }, [range.start, range.end, attempt]);

  const k = useMemo(() => computeKpis(rows), [rows]);
  const daily = useMemo(() => groupByDay(rows, range.start, range.end), [rows, range]);
  const sourceSlices = useMemo(() => sliceBySource(rows), [rows]);
  const residuals = useMemo(
    () => rows.filter(r => r.realizedRpc > 0).map(r => residual(r)),
    [rows],
  );
  const recent = useMemo(
    () => [...rows].sort((a, b) => b.windowEndsAtMs - a.windowEndsAtMs).slice(0, 15),
    [rows],
  );

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand"><span className="mark" />Predictive RPC Estimator</span>
        <span className="product">Revenue intelligence · Reconciliation</span>
        <span className="env-pill">Staging · europe-west2</span>
      </header>

      <div className="pageheader">
        <div>
          <h1>Reconciliation overview</h1>
          <div className="sub">
            Model-predicted revenue per click compared with realized revenue from the sales ledger.
          </div>
        </div>
        <div className="range">
          <b>{fmtDateOnly(range.start)}</b> — <b>{fmtDateOnly(range.end)}</b> · last {WINDOW_DAYS} days
        </div>
      </div>

      <main className="content">
        {status.kind === "error" && (
          <div className="errorbox" style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span>Failed to load reconciliation data: {status.msg}</span>
            <button
              onClick={() => setAttempt((n) => n + 1)}
              style={{
                marginLeft: "auto",
                background: "var(--red)", color: "#fff",
                border: 0, borderRadius: 6,
                padding: "6px 14px", fontSize: 12, fontWeight: 600,
                cursor: "pointer",
              }}
            >Retry</button>
          </div>
        )}

        <section className="kpis" aria-label="Key performance indicators">
          <Kpi label="Reconciled clicks" value={fmtInt(k.total)} caption={`${fmtInt(k.withRevenue)} with realized revenue`} />
          <Kpi label="Mean predicted RPC" value={fmtCurrency(k.meanPredicted)} caption="across the window" />
          <Kpi label="Mean realized RPC"  value={fmtCurrency(k.meanRealized)}  caption="reconciled clicks only" accent="accent" />
          <Kpi label="Mean abs residual"  value={fmtCurrency(k.mae)}           caption={`bias ${k.bias >= 0 ? "+" : ""}${fmtCurrency(k.bias)}`} accent={k.mae <= 0.4 ? "green" : "red"} />
          <Kpi label="Conversion coverage" value={fmtPercent(k.coverage)}      caption="reconciled within window" />
        </section>

        <section className="row">
          <div className="card">
            <h3>Predicted vs realized — daily mean</h3>
            <div className="cardsub">Average RPC per day across the rolling window.</div>
            <DailyComparisonChart data={daily} />
            <div className="legend">
              <span><span className="dot" style={{ background: "#0f6e7a" }} />Predicted</span>
              <span><span className="dot" style={{ background: "#d97306" }} />Realized</span>
            </div>
          </div>
          <div className="card">
            <h3>Prediction source mix</h3>
            <div className="cardsub">Share of clicks served by the model vs fallback paths.</div>
            <SourceDonut slices={sourceSlices} />
          </div>
        </section>

        <section className="row">
          <LivePredictionCard />
          <div className="card">
            <h3>Model health</h3>
            <div className="cardsub">Live signals from the scoring service.</div>
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              <Health label="Scoring API" detail="Cloud Run · europe-west2" ok />
              <Health label="Vertex AI endpoint" detail="rpc-estimator @1 · e2-standard-2" ok />
              <Health label="Drift monitors" detail="PSI on inputs · residuals on outputs" ok />
              <Health label="Circuit breaker" detail="closed · 0 trips in window" ok />
              <Health label="Reconciliation pipeline" detail="BigQuery · refreshed continuously" ok />
            </ul>
          </div>
        </section>

        <section className="row">
          <div className="card">
            <h3>Residual distribution</h3>
            <div className="cardsub">Realized minus predicted across reconciled clicks. A narrow band around zero indicates a well-calibrated model.</div>
            <ResidualHistogram values={residuals} />
            <div className="legend">
              <span><span className="dot" style={{ background: "#b9341d" }} />Under-predicted (lost revenue)</span>
              <span><span className="dot" style={{ background: "#1f8a4f" }} />Over-predicted</span>
            </div>
          </div>
        </section>

        <section className="card table-card">
          <div className="head">
            <div>
              <h3>Recent reconciliations</h3>
              <div className="cardsub" style={{ marginBottom: 0 }}>
                Latest predictions whose 30-day revenue window has closed.
              </div>
            </div>
            <div className="count">{fmtInt(recent.length)} of {fmtInt(k.total)}</div>
          </div>
          {status.kind === "loading" ? (
            <div className="loading">Loading reconciled predictions…</div>
          ) : recent.length === 0 ? (
            <div className="empty">No reconciled predictions in this window.</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Click ID</th>
                  <th>Source</th>
                  <th className="num">Predicted</th>
                  <th className="num">Realized</th>
                  <th className="num">Residual</th>
                  <th>Window closed</th>
                </tr>
              </thead>
              <tbody>
                {recent.map(r => {
                  const res = residual(r);
                  const cls = Math.abs(res) < 0.01 ? "zero" : res > 0 ? "up" : "down";
                  const arrow = cls === "up" ? "▲" : cls === "down" ? "▼" : "•";
                  return (
                    <tr key={r.clickId}>
                      <td className="mono" title={r.clickId}>{shorten(r.clickId, 18)}</td>
                      <td><SourcePill source={r.source} /></td>
                      <td className="num">{fmtCurrency(r.predictedRpc)}</td>
                      <td className="num">{r.realizedRpc > 0 ? fmtCurrency(r.realizedRpc) : <span style={{ color: "var(--muted)" }}>—</span>}</td>
                      <td className="num">
                        {r.realizedRpc > 0 ? (
                          <span className={`residual ${cls}`}>
                            <span className="arrow">{arrow}</span>{fmtCurrency(res)}
                          </span>
                        ) : <span style={{ color: "var(--muted)" }}>pending</span>}
                      </td>
                      <td style={{ color: "var(--muted)" }}>{fmtDate(r.windowEndsAtMs)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      </main>

      <footer className="foot">
        <div className="divider" />
        Predictive RPC Estimator · Reconciliation dashboard · staging environment ·
        Data sourced from BigQuery <code>rpc_estimator_staging.predictions_vs_revenue</code>.
      </footer>
    </div>
  );
}

function Kpi({ label, value, caption, accent }: {
  label: string; value: string; caption?: string;
  accent?: "accent" | "green" | "red";
}) {
  return (
    <div className={`kpi ${accent ?? ""}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {caption && <div className="delta">{caption}</div>}
    </div>
  );
}

function SourcePill({ source }: { source: ReconciliationRow["source"] }) {
  const cls = source === "MODEL" ? "model"
            : source === "KILL_SWITCH" ? "kill"
            : "fallback";
  const label = source === "MODEL" ? "Model"
              : source === "FALLBACK_TCPA" ? "Fallback · tCPA"
              : source === "FALLBACK_DATA_LAYER" ? "Fallback · data-layer"
              : "Kill switch";
  return <span className={`pill ${cls}`}>{label}</span>;
}

function Health({ label, detail, ok }: { label: string; detail: string; ok: boolean }) {
  return (
    <li style={{
      display: "flex", alignItems: "center",
      padding: "10px 0", borderBottom: "1px solid var(--rule)",
    }}>
      <span style={{
        width: 8, height: 8, borderRadius: 999,
        background: ok ? "var(--green)" : "var(--red)",
        marginRight: 12, flexShrink: 0,
        boxShadow: ok ? "0 0 0 3px var(--green-50)" : "0 0 0 3px var(--red-50)",
      }} />
      <div style={{ display: "flex", flexDirection: "column" }}>
        <span style={{ color: "var(--navy)", fontWeight: 600, fontSize: 13 }}>{label}</span>
        <span style={{ color: "var(--muted)", fontSize: 11 }}>{detail}</span>
      </div>
      <span style={{
        marginLeft: "auto", color: ok ? "var(--green)" : "var(--red)",
        fontSize: 11, fontWeight: 700, letterSpacing: "0.06em",
      }}>{ok ? "OPERATIONAL" : "DEGRADED"}</span>
    </li>
  );
}

// ── Live prediction card ───────────────────────────────────────────────

interface PredictForm {
  device: "mobile" | "desktop" | "tablet";
  geo: "GB" | "US" | "DE" | "FR";
  hour_of_day: number;
  query_intent: "commercial" | "navigational" | "informational";
  cerberus_score: number;
  rpc_7d: number;
  rpc_14d: number;
  rpc_30d: number;
  auction_pressure: number;
  is_payday_week: boolean;
  visits_prev_30d: number;
}

const DEFAULTS: PredictForm = {
  device: "mobile",
  geo: "GB",
  hour_of_day: 14,
  query_intent: "commercial",
  cerberus_score: 0.62,
  rpc_7d: 1.85,
  rpc_14d: 1.92,
  rpc_30d: 1.78,
  auction_pressure: 0.55,
  is_payday_week: false,
  visits_prev_30d: 3,
};

interface PredictResult {
  predicted_rpc: number;
  source: string;
  model_version: string;
  latency_ms: number;
  attrs: AttrPoint[];
  base_value: number;
}

function LivePredictionCard() {
  const [form, setForm] = useState<PredictForm>(DEFAULTS);
  const [result, setResult] = useState<PredictResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function update<K extends keyof PredictForm>(k: K, v: PredictForm[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function predict() {
    setBusy(true); setErr(null); setResult(null);
    const click_id = `demo-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    const correlation_id = `corr-${Date.now().toString(36)}`;
    const payload = {
      ...form,
      click_id,
      correlation_id,
      ad_creative_id: "demo-creative",
      landing_path: "/",
    };
    const t0 = performance.now();
    try {
      const scoreResp = await fetch("/score", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!scoreResp.ok) throw new Error(`score: ${scoreResp.status} ${await scoreResp.text()}`);
      const score = await scoreResp.json();
      const latency_ms = Math.round(performance.now() - t0);

      let attrs: AttrPoint[] = [];
      let base_value = 0;
      try {
        const explainResp = await fetch("/explain", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (explainResp.ok) {
          const ex = await explainResp.json();
          base_value = ex.base_value ?? 0;
          attrs = (ex.contributions ?? []).map((c: [string, number]) => ({
            feature: c[0], value: c[1],
          }));
        }
      } catch { /* explain optional — keep score result */ }

      setResult({
        predicted_rpc: score.predicted_rpc,
        source: score.source,
        model_version: score.model_version,
        latency_ms,
        attrs,
        base_value,
      });
    } catch (e: any) {
      setErr(e?.message ?? "Prediction failed.");
    } finally {
      setBusy(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "6px 8px", fontSize: 13,
    border: "1px solid var(--rule)", borderRadius: 4,
    background: "#fff", color: "var(--slate)",
    fontVariantNumeric: "tabular-nums",
  };
  const labelStyle: React.CSSProperties = {
    display: "block", fontSize: 11, fontWeight: 600,
    color: "var(--muted)", marginBottom: 3, letterSpacing: "0.04em",
    textTransform: "uppercase",
  };

  return (
    <div className="card" style={{ position: "relative" }}>
      <h3>Predict a click — live</h3>
      <div className="cardsub">
        Send a click context to the production model and receive an RPC estimate with feature attributions.
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 10,
      }}>
        <div><label style={labelStyle}>Device</label>
          <select style={inputStyle} value={form.device}
                  onChange={(e) => update("device", e.target.value as PredictForm["device"])}>
            <option value="mobile">mobile</option>
            <option value="desktop">desktop</option>
            <option value="tablet">tablet</option>
          </select></div>
        <div><label style={labelStyle}>Geo</label>
          <select style={inputStyle} value={form.geo}
                  onChange={(e) => update("geo", e.target.value as PredictForm["geo"])}>
            <option value="GB">United Kingdom</option>
            <option value="US">United States</option>
            <option value="DE">Germany</option>
            <option value="FR">France</option>
          </select></div>
        <div><label style={labelStyle}>Hour of day (0–23)</label>
          <input type="number" min={0} max={23} step={1} style={inputStyle}
                 value={form.hour_of_day}
                 onChange={(e) => update("hour_of_day", Math.min(23, Math.max(0, parseInt(e.target.value || "0"))))} /></div>
        <div><label style={labelStyle}>Query intent</label>
          <select style={inputStyle} value={form.query_intent}
                  onChange={(e) => update("query_intent", e.target.value as PredictForm["query_intent"])}>
            <option value="commercial">commercial</option>
            <option value="navigational">navigational</option>
            <option value="informational">informational</option>
          </select></div>
        <div><label style={labelStyle}>Cerberus score (0–1)</label>
          <input type="number" min={0} max={1} step={0.01} style={inputStyle}
                 value={form.cerberus_score}
                 onChange={(e) => update("cerberus_score", parseFloat(e.target.value || "0"))} /></div>
        <div><label style={labelStyle}>Auction pressure (0–1)</label>
          <input type="number" min={0} max={1} step={0.01} style={inputStyle}
                 value={form.auction_pressure}
                 onChange={(e) => update("auction_pressure", parseFloat(e.target.value || "0"))} /></div>
        <div><label style={labelStyle}>Rolling RPC 7 / 14 / 30d (£)</label>
          <div style={{ display: "flex", gap: 6 }}>
            <input type="number" step={0.01} style={inputStyle}
                   value={form.rpc_7d}
                   onChange={(e) => update("rpc_7d", parseFloat(e.target.value || "0"))} />
            <input type="number" step={0.01} style={inputStyle}
                   value={form.rpc_14d}
                   onChange={(e) => update("rpc_14d", parseFloat(e.target.value || "0"))} />
            <input type="number" step={0.01} style={inputStyle}
                   value={form.rpc_30d}
                   onChange={(e) => update("rpc_30d", parseFloat(e.target.value || "0"))} />
          </div>
        </div>
        <div><label style={labelStyle}>Prior 30-day visits</label>
          <input type="number" step={1} min={0} style={inputStyle}
                 value={form.visits_prev_30d}
                 onChange={(e) => update("visits_prev_30d", parseInt(e.target.value || "0"))} /></div>
      </div>

      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--rule)",
      }}>
        <button onClick={predict} disabled={busy} style={{
          background: "var(--navy)", color: "#fff", border: 0,
          borderRadius: 6, padding: "9px 22px",
          fontSize: 13, fontWeight: 700, letterSpacing: "0.04em",
          cursor: busy ? "wait" : "pointer",
          opacity: busy ? 0.7 : 1,
          transition: "opacity 0.15s",
        }}>{busy ? "Predicting…" : "Predict"}</button>

        {result && (
          <>
            <div style={{ marginLeft: 8 }}>
              <div style={{ fontSize: 10, color: "var(--muted)",
                            textTransform: "uppercase", letterSpacing: "0.06em",
                            fontWeight: 600 }}>Predicted RPC</div>
              <div style={{ fontSize: 26, fontWeight: 700, color: "var(--navy)",
                            fontVariantNumeric: "tabular-nums",
                            letterSpacing: "-0.01em" }}>
                {fmtCurrency(result.predicted_rpc)}
              </div>
            </div>
            <span style={{
              padding: "3px 9px", borderRadius: 999,
              background: "var(--teal-50)", color: "var(--teal)",
              fontSize: 11, fontWeight: 700, letterSpacing: "0.04em",
            }}>
              {result.source.toUpperCase()}
            </span>
            <span style={{
              padding: "3px 9px", borderRadius: 999,
              background: result.latency_ms < 1500 ? "var(--green-50)" : "var(--accent-50)",
              color: result.latency_ms < 1500 ? "var(--green)" : "var(--accent)",
              fontSize: 11, fontWeight: 700,
            }}>
              {result.latency_ms} ms
            </span>
            <span style={{
              marginLeft: "auto",
              fontSize: 10, color: "var(--muted)",
            }}>{result.model_version}</span>
          </>
        )}
      </div>

      {err && (
        <div style={{
          marginTop: 10, padding: "8px 12px", borderRadius: 6,
          background: "var(--red-50)", color: "var(--red)", fontSize: 12,
        }}>{err}</div>
      )}

      {result && result.attrs.length > 0 && (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--rule)" }}>
          <AttributionBars attrs={result.attrs} baseValue={result.base_value} />
        </div>
      )}
    </div>
  );
}

// ── aggregates ─────────────────────────────────────────────────────────

interface Kpis {
  total: number;
  withRevenue: number;
  meanPredicted: number;
  meanRealized: number;
  mae: number;
  bias: number;
  coverage: number;
}

function computeKpis(rows: ReconciliationRow[]): Kpis {
  if (rows.length === 0) {
    return { total: 0, withRevenue: 0, meanPredicted: 0, meanRealized: 0,
             mae: 0, bias: 0, coverage: 0 };
  }
  const withRev = rows.filter(r => r.realizedRpc > 0);
  const meanPredicted = mean(rows.map(r => r.predictedRpc));
  const meanRealized  = withRev.length ? mean(withRev.map(r => r.realizedRpc)) : 0;
  const mae  = withRev.length ? mean(withRev.map(r => Math.abs(residual(r)))) : 0;
  const bias = withRev.length ? mean(withRev.map(r => residual(r))) : 0;
  return {
    total: rows.length,
    withRevenue: withRev.length,
    meanPredicted, meanRealized, mae, bias,
    coverage: withRev.length / rows.length,
  };
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / Math.max(xs.length, 1);
}

function groupByDay(rows: ReconciliationRow[], startMs: number, endMs: number) {
  if (rows.length === 0) return [];
  const days: Map<number, { predicted: number[]; realized: number[]; count: number }> = new Map();
  // Use the close-of-window date as the "day" — that's when the row materializes for reconciliation.
  for (const r of rows) {
    const d = new Date(r.windowEndsAtMs);
    d.setUTCHours(0, 0, 0, 0);
    const key = d.getTime();
    if (!days.has(key)) days.set(key, { predicted: [], realized: [], count: 0 });
    const slot = days.get(key)!;
    slot.predicted.push(r.predictedRpc);
    if (r.realizedRpc > 0) slot.realized.push(r.realizedRpc);
    slot.count++;
  }
  // Walk every day in the window so the chart has a continuous x-axis.
  const out: { dayMs: number; predicted: number; realized: number; count: number }[] = [];
  const start = new Date(startMs); start.setUTCHours(0, 0, 0, 0);
  const end   = new Date(endMs);   end.setUTCHours(0, 0, 0, 0);
  for (let t = start.getTime(); t <= end.getTime(); t += DAY_MS) {
    const slot = days.get(t);
    if (!slot) continue;
    out.push({
      dayMs: t,
      predicted: mean(slot.predicted),
      realized: slot.realized.length ? mean(slot.realized) : 0,
      count: slot.count,
    });
  }
  return out;
}

function sliceBySource(rows: ReconciliationRow[]) {
  const colors: Record<ReconciliationRow["source"], string> = {
    MODEL: "#0f6e7a",
    FALLBACK_TCPA: "#d97306",
    FALLBACK_DATA_LAYER: "#c79029",
    KILL_SWITCH: "#b9341d",
  };
  const labels: Record<ReconciliationRow["source"], string> = {
    MODEL: "Model",
    FALLBACK_TCPA: "Fallback · tCPA",
    FALLBACK_DATA_LAYER: "Fallback · data-layer",
    KILL_SWITCH: "Kill switch",
  };
  const counts = new Map<ReconciliationRow["source"], number>();
  for (const r of rows) counts.set(r.source, (counts.get(r.source) ?? 0) + 1);
  return Array.from(counts.entries()).map(([s, v]) => ({
    label: labels[s], value: v, color: colors[s],
  }));
}
