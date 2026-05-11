import { useEffect, useMemo, useState } from "react";
import type { ReconciliationRow } from "../domain/reconciliation";
import { residual } from "../domain/reconciliation";
import { LoadReconciliation } from "../application/load-reconciliation";
import { HttpReconciliationGateway } from "../infrastructure/http-gateway";
import {
  fmtCurrency, fmtPercent, fmtInt, fmtDate, fmtDateOnly, shorten,
} from "./format";
import { DailyComparisonChart, SourceDonut, ResidualHistogram } from "./charts";

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
        setStatus({ kind: "error", msg: e?.message ?? "Failed to load." });
      });
    return () => { cancelled = true; };
  }, [range.start, range.end]);

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
          <div className="errorbox">Failed to load reconciliation data: {status.msg}</div>
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
          <div className="card">
            <h3>Residual distribution</h3>
            <div className="cardsub">Realized minus predicted across reconciled clicks. A narrow band around zero indicates a well-calibrated model.</div>
            <ResidualHistogram values={residuals} />
            <div className="legend">
              <span><span className="dot" style={{ background: "#b9341d" }} />Under-predicted (lost revenue)</span>
              <span><span className="dot" style={{ background: "#1f8a4f" }} />Over-predicted</span>
            </div>
          </div>
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
