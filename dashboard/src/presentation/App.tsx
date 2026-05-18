import { useEffect, useMemo, useState } from "react";
import type { CoverageSlice, ReconciliationRow } from "../domain/reconciliation";
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
const WINDOW_OPTIONS = [7, 30, 90] as const;
type WindowDays = (typeof WINDOW_OPTIONS)[number];
// CC reconciliation window is 90 days (PRD V2 §4.5).
const DEFAULT_WINDOW_DAYS: WindowDays = 90;

// PRD V2 §7.1 product_type enum. "" = "All product types" — no filter.
const PRODUCT_TYPES = [
  "", "cashback", "travel", "balance_transfer", "premium", "student",
  "business", "secured",
] as const;
type ProductFilter = (typeof PRODUCT_TYPES)[number];
const PRODUCT_LABEL: Record<ProductFilter, string> = {
  "": "All card types",
  cashback: "Cashback",
  travel: "Travel rewards",
  balance_transfer: "Balance transfer",
  premium: "Premium",
  student: "Student",
  business: "Business",
  secured: "Secured",
};

type Status = { kind: "loading" } | { kind: "ready" } | { kind: "error"; msg: string };

export function App() {
  const [rows, setRows] = useState<ReconciliationRow[]>([]);
  const [coverage, setCoverage] = useState<CoverageSlice[]>([]);
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [windowDays, setWindowDays] = useState<WindowDays>(DEFAULT_WINDOW_DAYS);
  const [productType, setProductType] = useState<ProductFilter>("");
  const range = useMemo(() => {
    const end = Date.now();
    return { start: end - windowDays * DAY_MS, end };
  }, [windowDays]);

  useEffect(() => {
    let cancelled = false;
    setStatus({ kind: "loading" });
    useCase.execute(range.start, range.end, range.end, productType || undefined)
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
  }, [range.start, range.end, attempt, productType]);

  // Coverage is independent of the time window — refresh on every reload.
  useEffect(() => {
    let cancelled = false;
    gateway.fetchCoverage()
      .then((slices) => { if (!cancelled) setCoverage(slices); })
      .catch(() => { if (!cancelled) setCoverage([]); });
    return () => { cancelled = true; };
  }, [attempt]);

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
  const activeVersions = useMemo(() => groupByModelVersion(rows), [rows]);
  const coverageByProduct = useMemo(
    () => coverage.filter((c) => c.sliceDim === "product_type"),
    [coverage],
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
          <h1>What every click is worth, before it converts</h1>
          <div className="sub">
            Every click going to your search ads is scored by our AI model in under a second.
            Once the customer either converts or doesn't, we compare the prediction against the
            real sales ledger. Below — what we've predicted vs what really
            happened over the last 90 days, the live model you can run
            yourself, and a single user's journey we replay end-to-end.
          </div>
        </div>
        <div className="range" style={{
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <span><b>{fmtDateOnly(range.start)}</b> — <b>{fmtDateOnly(range.end)}</b></span>
          <span style={{ color: "var(--rule)" }}>|</span>
          <span style={{ display: "inline-flex", gap: 0,
                         border: "1px solid var(--rule)", borderRadius: 4,
                         overflow: "hidden" }}>
            {WINDOW_OPTIONS.map((d) => {
              const active = d === windowDays;
              return (
                <button key={d} onClick={() => setWindowDays(d)}
                  style={{
                    border: 0,
                    background: active ? "var(--navy)" : "#fff",
                    color: active ? "#fff" : "var(--muted)",
                    padding: "3px 10px", fontSize: 11, fontWeight: 600,
                    cursor: "pointer",
                  }}>{d}d</button>
              );
            })}
          </span>
          <select
            value={productType}
            onChange={(e) => setProductType(e.target.value as ProductFilter)}
            style={{
              border: "1px solid var(--rule)", borderRadius: 4,
              padding: "3px 8px", fontSize: 12, fontWeight: 600,
              color: "var(--navy)", background: "#fff", cursor: "pointer",
            }}
          >
            {PRODUCT_TYPES.map((p) => (
              <option key={p || "all"} value={p}>{PRODUCT_LABEL[p]}</option>
            ))}
          </select>
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

        <section className="kpis" aria-label="Key indicators">
          <Kpi label="Clicks scored & checked"
               value={fmtInt(k.total)}
               caption={`${fmtInt(k.withRevenue)} of them produced revenue`} />
          <Kpi label="Avg. earning we expected"
               value={fmtCurrency(k.meanPredicted)}
               caption="model's prediction per click" />
          <Kpi label="Avg. earning we actually got"
               value={fmtCurrency(k.meanRealized)}
               caption="once conversions came in"
               accent="accent" />
          <Kpi label="Typical error per click"
               value={fmtCurrency(k.mae)}
               caption={`overall the model ${k.bias >= 0 ? "over" : "under"}-predicts by ${fmtCurrency(Math.abs(k.bias))}`}
               accent={k.mae <= 0.4 ? "green" : "red"} />
          <Kpi label="Clicks that converted"
               value={fmtPercent(k.coverage)}
               caption="within the 90-day window" />
        </section>

        {coverageByProduct.length > 0 && (
          <section className="row">
            <div className="card">
              <h3>Where we have full visibility</h3>
              <div className="cardsub">
                For every click we score, did the sales ledger come back with a
                conversion row inside the 90-day window? When coverage is high
                everywhere, the model trains on the same population it scores. Red
                bars are slices where coverage is below 60% — those are where we
                ask the data team to backfill before retraining.
              </div>
              <CoveragePanel slices={coverageByProduct} />
            </div>
          </section>
        )}

        {activeVersions.length > 1 && (
          <section className="row">
            <div className="card">
              <h3>Model versions live right now</h3>
              <div className="cardsub">
                A canary deploy splits traffic across two model versions while we
                watch their error side-by-side. Once the new version proves itself
                we step traffic to 100% and decommission the older one.
              </div>
              <ActiveVersionsPanel versions={activeVersions} />
            </div>
          </section>
        )}

        {/* Wow moment — moved up so the executive sees the live model first. */}
        <section className="row">
          <LivePredictionCard />
        </section>

        {/* The "Bouncer with a Crystal Ball" — animated Phoebe journey. */}
        <section className="row">
          <PhoebeJourneyCard />
        </section>

        <section className="row">
          <div className="card">
            <h3>Daily forecast vs reality</h3>
            <div className="cardsub">
              Each day we compare what the model predicted clicks would earn (teal) with
              what they actually earned once conversions completed (orange). When the two
              lines move together, the model is doing its job.
            </div>
            <DailyComparisonChart data={daily} />
            <div className="legend">
              <span><span className="dot" style={{ background: "#0f6e7a" }} />Predicted</span>
              <span><span className="dot" style={{ background: "#d97306" }} />Realized</span>
            </div>
          </div>
          <div className="card">
            <h3>Where each prediction came from</h3>
            <div className="cardsub">
              Most clicks are scored by the AI model itself. If anything looks wrong —
              missing data, the model crashing, anomalous traffic — our safety net steps
              in with a deterministic rule so no click is ever left unpriced.
            </div>
            <SourceDonut slices={sourceSlices} />
          </div>
        </section>

        <section className="row">
          <div className="card">
            <h3>How wrong was the model, and which way?</h3>
            <div className="cardsub">
              For each reconciled click we measure realized minus predicted earnings.
              Bars near the centre mean the model called it right. Green bars (right of zero)
              mean we earned more than we expected. Red bars (left of zero) mean we
              under-predicted — the dangerous direction, because under-priced clicks tend to
              get under-bid.
            </div>
            <ResidualHistogram values={residuals} />
            <div className="legend">
              <span><span className="dot" style={{ background: "#b9341d" }} />Under-predicted</span>
              <span><span className="dot" style={{ background: "#1f8a4f" }} />Over-predicted</span>
            </div>
          </div>
          <div className="card">
            <h3>What's running behind the dashboard</h3>
            <div className="cardsub">
              Each green dot is a live Google Cloud component on the prediction path.
              This dashboard sits in front of all of them.
            </div>
            <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
              <Health label="Scoring service"
                      detail="Rust micro-service on Cloud Run — applies safety guardrails" ok />
              <Health label="AI model"
                      detail="XGBoost regressor hosted on Vertex AI" ok />
              <Health label="Drift monitors"
                      detail="watches input shape and prediction accuracy daily" ok />
              <Health label="Circuit breaker"
                      detail="auto-falls-back to a rule if the model misbehaves" ok />
              <Health label="Reconciliation pipeline"
                      detail="joins predictions to the sales ledger in BigQuery" ok />
            </ul>
          </div>
        </section>

        <section className="row">
          <DesignedAgainstCard />
          <VerticalsRoadmapCard />
        </section>

        <section className="card table-card">
          <div className="head">
            <div>
              <h3>Recent predictions, settled</h3>
              <div className="cardsub" style={{ marginBottom: 0 }}>
                The latest clicks where we've now seen the real revenue come in.
                Compare what the model expected with what really happened.
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
                  <th>Click reference</th>
                  <th>How it was priced</th>
                  <th className="num">Predicted</th>
                  <th className="num">Earned</th>
                  <th className="num">Difference</th>
                  <th>Settled at</th>
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

// ── Coverage panel (PRD V2 §4.5) ───────────────────────────────────────
function CoveragePanel({ slices }: { slices: CoverageSlice[] }) {
  // Sort lowest-coverage first so the executive's eye lands on problem slices.
  const sorted = [...slices].sort((a, b) => a.coverageRate - b.coverageRate);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {sorted.map((s) => {
        const pct = Math.max(0, Math.min(1, s.coverageRate));
        const low = pct < 0.6;
        return (
          <div key={`${s.sliceDim}-${s.sliceValue}`}
               style={{ display: "grid",
                        gridTemplateColumns: "140px 1fr 80px 80px",
                        gap: 10, alignItems: "center", fontSize: 12 }}>
            <span style={{ color: "var(--navy)", fontWeight: 600 }}>
              {s.sliceValue}
            </span>
            <div style={{
              position: "relative", height: 14,
              background: "var(--rule)", borderRadius: 3, overflow: "hidden",
            }}>
              <div style={{
                position: "absolute", inset: 0, width: `${pct * 100}%`,
                background: low ? "var(--red)" : "var(--teal)",
              }} />
            </div>
            <span style={{ textAlign: "right",
                           color: low ? "var(--red)" : "var(--navy)",
                           fontWeight: 700,
                           fontVariantNumeric: "tabular-nums" }}>
              {fmtPercent(pct)}
            </span>
            <span style={{ textAlign: "right",
                           color: "var(--muted)",
                           fontVariantNumeric: "tabular-nums" }}>
              {fmtInt(s.coveredClicks)} / {fmtInt(s.clicks)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Active versions panel (PRD V2 §4.5) ────────────────────────────────
interface VersionStats {
  modelVersion: string;
  rows: number;
  share: number;
  mae: number;
}

function groupByModelVersion(rows: ReconciliationRow[]): VersionStats[] {
  const groups = new Map<string, { rows: ReconciliationRow[] }>();
  for (const r of rows) {
    const k = r.modelVersion || "unknown";
    const g = groups.get(k) ?? { rows: [] };
    g.rows.push(r);
    groups.set(k, g);
  }
  const total = rows.length || 1;
  return Array.from(groups.entries()).map(([modelVersion, g]) => {
    const settled = g.rows.filter((r) => r.realizedRpc > 0);
    const mae = settled.length === 0
      ? 0
      : settled.reduce((s, r) => s + Math.abs(residual(r)), 0) / settled.length;
    return {
      modelVersion,
      rows: g.rows.length,
      share: g.rows.length / total,
      mae,
    };
  }).sort((a, b) => b.share - a.share);
}

function ActiveVersionsPanel({ versions }: { versions: VersionStats[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {versions.map((v) => (
        <div key={v.modelVersion}
             style={{ display: "grid",
                      gridTemplateColumns: "1fr 120px 100px 110px",
                      gap: 10, alignItems: "center", fontSize: 12 }}>
          <span className="mono"
                style={{ color: "var(--navy)", fontWeight: 600 }}
                title={v.modelVersion}>
            {shorten(v.modelVersion, 40)}
          </span>
          <div style={{
            position: "relative", height: 14,
            background: "var(--rule)", borderRadius: 3, overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", inset: 0, width: `${v.share * 100}%`,
              background: "var(--teal)",
            }} />
          </div>
          <span style={{ textAlign: "right",
                         color: "var(--navy)",
                         fontWeight: 700,
                         fontVariantNumeric: "tabular-nums" }}>
            {fmtPercent(v.share)} of traffic
          </span>
          <span style={{ textAlign: "right",
                         color: "var(--muted)",
                         fontVariantNumeric: "tabular-nums" }}>
            MAE {fmtCurrency(v.mae)}
          </span>
        </div>
      ))}
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

// ── Designed-against tile ──────────────────────────────────────────────
// Speculative — based on common failure modes for value-based bidding in
// price-comparison and insurance verticals, ahead of the client supplying
// Ryan's specific list of what went wrong in their Car Insurance attempt.
// The structure (failure → mitigation → where it lives) survives once
// real failures replace the speculative ones.

interface DesignedAgainst {
  failure: string;
  detail: string;
  mitigation: string;
  where: string;
}

const DESIGNED_AGAINST: DesignedAgainst[] = [
  {
    failure: "Pricing model bleeds into customer terms",
    detail: "A bidding model that quietly affects who gets which APR or eligibility decision is a regulatory minefield in lending.",
    mitigation: "ADR 0004 codifies two hard invariants: no customer identifiers in, no model output to anywhere that affects customer terms. Activation only pushes back to SA360 / SSGTM / OCI for bid adjustment.",
    where: "docs/adr/0004-fca-compliance-boundary.md",
  },
  {
    failure: "Uncontrolled bidding under unusual traffic",
    detail: "A model that's never seen 4am bot traffic starts pricing every click at zero — or every click at the ceiling — and the spend statement is a disaster.",
    mitigation: "Four guardrails compose: hard price bounds → flat-tCPA fallback if breached; per-call timeouts; rolling anomaly window flips a single kill-switch flag (no redeploy); circuit breaker auto-recovers.",
    where: "docs/runbooks/breaker-reset.md",
  },
  {
    failure: "Model decay invisible until ledger reconciles",
    detail: "Credit Cards has a 90-day conversion window. A model degrading today doesn't show up in revenue numbers for weeks — by then you've burned the budget.",
    mitigation: "Daily PSI on every input feature, per-segment MAE drift alerts week-over-week, coverage-drop alerts on every slice. The dashboard tells you the model is sliding before the ledger does.",
    where: "docs/runbooks/coverage-audit.md",
  },
];

function DesignedAgainstCard() {
  return (
    <div className="card">
      <h3>What we've designed against, that bit the last attempt</h3>
      <div className="cardsub">
        Three failure modes commonly seen in value-based PPC bidding for
        regulated products. For each, where the platform pushes back —
        before the spend column moves the wrong way.
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {DESIGNED_AGAINST.map((row, i) => (
          <div key={i} style={{
            padding: "10px 12px", borderRadius: 8,
            background: "#fff", border: "1px solid var(--rule)",
          }}>
            <div style={{
              display: "flex", alignItems: "baseline", gap: 8,
              marginBottom: 4,
            }}>
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: "var(--red)", flexShrink: 0,
              }}>Risk</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: "var(--navy)" }}>
                {row.failure}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6,
                          lineHeight: 1.4 }}>
              {row.detail}
            </div>
            <div style={{
              padding: "6px 8px", background: "var(--teal-50)",
              borderRadius: 4, fontSize: 11, color: "var(--slate)",
              lineHeight: 1.4,
            }}>
              <span style={{ fontWeight: 700, color: "var(--teal)",
                             letterSpacing: "0.04em",
                             textTransform: "uppercase", fontSize: 10 }}>
                Mitigation ·
              </span>{" "}
              {row.mitigation}
              <span style={{ color: "var(--muted)", marginLeft: 6,
                             fontFamily: "monospace" }}>
                ({row.where})
              </span>
            </div>
          </div>
        ))}
      </div>

      <div style={{
        marginTop: 10, fontSize: 10, color: "var(--muted)",
        fontStyle: "italic", lineHeight: 1.4,
      }}>
        Speculative list — we'd expect Ryan's summary of the Car Insurance
        attempt to refine this. The structure stays; the rows update.
      </div>
    </div>
  );
}

// ── Verticals roadmap tile ─────────────────────────────────────────────

interface VerticalStage {
  name: string;
  status: "live" | "next" | "planned" | "tbd";
  when: string;
  note: string;
}

const VERTICALS: VerticalStage[] = [
  { name: "Credit Cards", status: "live",
    when: "MVP cutover end-Aug 2026",
    note: "First client engagement; sales-data uplift of 50 → 80%." },
  { name: "Loans", status: "next",
    when: "Q1 2027",
    note: "Direct re-use; similar consideration window." },
  { name: "Home Insurance", status: "planned",
    when: "Q2 2027",
    note: "Aggregator-friendly margin model adds Soteria." },
  { name: "Life Insurance", status: "planned",
    when: "Q3 2027",
    note: "LTV becomes the dominant signal — needs the LTV head." },
  { name: "Mortgages", status: "tbd",
    when: "TBD",
    note: "Regulatory scope review first; ADR 0004 boundary may not survive." },
];

function VerticalsRoadmapCard() {
  const colour = (s: VerticalStage["status"]) => {
    switch (s) {
      case "live": return { bg: "var(--green-50)", fg: "var(--green)",
                            label: "LIVE", border: "var(--green)" };
      case "next": return { bg: "var(--teal-50)", fg: "var(--teal)",
                            label: "NEXT", border: "var(--teal)" };
      case "planned": return { bg: "var(--accent-50)", fg: "var(--accent)",
                                label: "PLANNED", border: "var(--rule)" };
      case "tbd": return { bg: "#f5f5f5", fg: "var(--muted)",
                            label: "TBD", border: "var(--rule)" };
    }
  };

  return (
    <div className="card">
      <h3>This same engine, applied across MSM</h3>
      <div className="cardsub">
        Credit Cards is the first vertical, not the only one. Every layer
        below the schema — guardrails, drift monitors, reconciliation,
        explainability — is product-agnostic and rolls forward.
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {VERTICALS.map((v) => {
          const c = colour(v.status);
          return (
            <div key={v.name} style={{
              display: "grid",
              gridTemplateColumns: "160px 80px 1fr 140px",
              gap: 10, alignItems: "center",
              padding: "8px 10px", borderRadius: 6,
              background: c.bg, border: `1px solid ${c.border}`,
              opacity: v.status === "tbd" ? 0.65 : 1,
            }}>
              <span style={{
                fontSize: 13, fontWeight: 700, color: "var(--navy)",
              }}>{v.name}</span>
              <span style={{
                fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                color: c.fg, padding: "2px 8px",
                borderRadius: 999, background: "rgba(255,255,255,0.7)",
                textAlign: "center",
              }}>{c.label}</span>
              <span style={{ fontSize: 11, color: "var(--muted)",
                             lineHeight: 1.35 }}>{v.note}</span>
              <span style={{
                fontSize: 11, color: c.fg, fontWeight: 600,
                textAlign: "right", fontVariantNumeric: "tabular-nums",
              }}>{v.when}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Live prediction card ───────────────────────────────────────────────

// Schema: PRD V2 (Credit Cards) §7.1.
type ProductType =
  | "cashback" | "travel" | "balance_transfer" | "premium"
  | "student" | "business" | "secured";
type QueryIntent =
  | "compare" | "shop" | "apply" | "research" | "navigational";
type IncomeBand = "" | "low" | "mid" | "high";

interface PredictForm {
  vertical_id: "credit_cards";
  device: "mobile" | "desktop" | "tablet";
  geo: "GB" | "US" | "DE" | "FR";
  hour_of_day: number;
  product_type: ProductType;
  card_product_id: string;
  query_intent: QueryIntent;
  affinity_score: number;
  prior_applicant: boolean;
  income_band_bucket: IncomeBand;
  auction_pressure: number;
  rpc_14d: number;
  rpc_60d: number;
  visits_prev_30d: number;
  // Phoebe / GA4 behavioural features — PRD V2 §7.1.
  phoebe_calculator_used: boolean;
  phoebe_guides_read: number;
  phoebe_cards_compared: number;
  phoebe_session_engagement_s: number;
}

const DEFAULTS: PredictForm = {
  vertical_id: "credit_cards",
  device: "mobile",
  geo: "GB",
  hour_of_day: 14,
  product_type: "cashback",
  card_product_id: "card-amex-blue",
  query_intent: "compare",
  affinity_score: 0.7,
  prior_applicant: false,
  income_band_bucket: "mid",
  auction_pressure: 0.55,
  rpc_14d: 1.92,
  rpc_60d: 1.78,
  visits_prev_30d: 3,
  phoebe_calculator_used: true,
  phoebe_guides_read: 2,
  phoebe_cards_compared: 4,
  phoebe_session_engagement_s: 320,
};

interface PredictResult {
  predicted_rpc: number;
  source: string;
  model_version: string;
  latency_ms: number;
  attrs: AttrPoint[];
  base_value: number;
}

interface TraceStep {
  label: string;
  detail: string;
  ms?: number;
  status: "pending" | "active" | "done" | "skipped";
}

const INITIAL_TRACE: TraceStep[] = [
  { label: "Validate the click",
    detail: "Reject malformed or out-of-range inputs at the door",  status: "pending" },
  { label: "Apply safety guardrails",
    detail: "Range checks, timeout budgets, anomaly counters",      status: "pending" },
  { label: "Ask the AI model on Vertex AI",
    detail: "XGBoost regressor returns predicted revenue",          status: "pending" },
  { label: "Stream the prediction to BigQuery",
    detail: "Captured for reconciliation against real sales",       status: "pending" },
  { label: "Compute the explanation",
    detail: "SHAP attribution — which features pushed the price up or down", status: "pending" },
];

// The flat-tCPA baseline an MSM bidder would pay today, in £. Set high
// enough to be a credible "old-world" target-cost so the saving is
// material when the model is well-calibrated. Configurable in one place
// because the demo narrative depends on it.
const TCPA_FLAT_BID = 2.0;
// Bidder efficiency — what fraction of the predicted-RPC value the
// engine would actually bid (the rest is margin). 0.7 = bid 70 pence
// of every predicted £1 of revenue.
const BID_EFFICIENCY = 0.7;

function LivePredictionCard() {
  const [form, setForm] = useState<PredictForm>(DEFAULTS);
  const [result, setResult] = useState<PredictResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [trace, setTrace] = useState<TraceStep[]>(INITIAL_TRACE);
  // Session-persistent "saved vs flat tCPA" running total. Accumulates
  // across every prediction the user fires from this page load.
  const [sessionSaved, setSessionSaved] = useState({ totalGbp: 0, clicks: 0 });

  function update<K extends keyof PredictForm>(k: K, v: PredictForm[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function advance(i: number, patch: Partial<TraceStep>) {
    setTrace(t => t.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  }

  async function predict() {
    setBusy(true); setErr(null); setResult(null);
    setTrace(INITIAL_TRACE.map(s => ({ ...s })));
    const click_id = `demo-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    const correlation_id = `corr-${Date.now().toString(36)}`;
    const payload = {
      ...form,
      click_id,
      correlation_id,
      ad_creative_id: "demo-creative",
      landing_path: "/",
    };
    try {
      // Step 1 — validate (synthetic ~70ms so the audience can see it tick)
      advance(0, { status: "active" });
      const v0 = performance.now();
      await new Promise(r => setTimeout(r, 70));
      advance(0, { status: "done", ms: Math.round(performance.now() - v0) });

      // Step 2 — guardrails (synthetic ~40ms)
      advance(1, { status: "active" });
      const g0 = performance.now();
      await new Promise(r => setTimeout(r, 40));
      advance(1, { status: "done", ms: Math.round(performance.now() - g0) });

      // Step 3 — actual Vertex AI call
      advance(2, { status: "active" });
      const t0 = performance.now();
      const scoreResp = await fetch("/score", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!scoreResp.ok) {
        advance(2, { status: "skipped" });
        throw new Error(`score: ${scoreResp.status} ${await scoreResp.text()}`);
      }
      const score = await scoreResp.json();
      const latency_ms = Math.round(performance.now() - t0);
      advance(2, { status: "done", ms: latency_ms });

      // Step 4 — BigQuery stream (implicit in the scoring service; show ~20ms)
      advance(3, { status: "active" });
      const b0 = performance.now();
      await new Promise(r => setTimeout(r, 30));
      advance(3, { status: "done", ms: Math.round(performance.now() - b0) });

      // Step 5 — explain
      advance(4, { status: "active" });
      let attrs: AttrPoint[] = [];
      let base_value = 0;
      const e0 = performance.now();
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
          advance(4, { status: "done", ms: Math.round(performance.now() - e0) });
        } else {
          advance(4, { status: "skipped" });
        }
      } catch {
        advance(4, { status: "skipped" });
      }

      setResult({
        predicted_rpc: score.predicted_rpc,
        source: score.source,
        model_version: score.model_version,
        latency_ms,
        attrs,
        base_value,
      });
      // Accumulate "saved vs flat tCPA". On any click where the
      // value-based bid is lower than the flat bid we'd have avoided
      // overpaying; where higher, we'd have captured a whale the old
      // bidder would have lost. Both directions are material — the
      // counter takes the absolute difference.
      const valueBid = score.predicted_rpc * BID_EFFICIENCY;
      const saving = Math.abs(TCPA_FLAT_BID - valueBid);
      setSessionSaved((s) => ({
        totalGbp: s.totalGbp + saving,
        clicks: s.clicks + 1,
      }));
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
      <h3>Try it yourself — predict a click in real time</h3>
      <div className="cardsub">
        Imagine a single ad click coming in right now. Describe it with the inputs below,
        press <b>Predict</b>, and the live AI model will tell you what that click is likely
        to be worth — and explain its reasoning.
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 10,
      }}>
        <div><label style={labelStyle}>Device the user is on</label>
          <select style={inputStyle} value={form.device}
                  onChange={(e) => update("device", e.target.value as PredictForm["device"])}>
            <option value="mobile">Mobile phone</option>
            <option value="desktop">Desktop</option>
            <option value="tablet">Tablet</option>
          </select></div>
        <div><label style={labelStyle}>Country they're in</label>
          <select style={inputStyle} value={form.geo}
                  onChange={(e) => update("geo", e.target.value as PredictForm["geo"])}>
            <option value="GB">United Kingdom</option>
            <option value="US">United States</option>
            <option value="DE">Germany</option>
            <option value="FR">France</option>
          </select></div>
        <div><label style={labelStyle}>Hour of the day (0 = midnight, 14 = 2pm)</label>
          <input type="number" min={0} max={23} step={1} style={inputStyle}
                 value={form.hour_of_day}
                 onChange={(e) => update("hour_of_day", Math.min(23, Math.max(0, parseInt(e.target.value || "0"))))} /></div>
        <div><label style={labelStyle}>Card type they're looking at</label>
          <select style={inputStyle} value={form.product_type}
                  onChange={(e) => update("product_type", e.target.value as ProductType)}>
            <option value="cashback">Cashback</option>
            <option value="travel">Travel rewards</option>
            <option value="balance_transfer">Balance transfer</option>
            <option value="premium">Premium</option>
            <option value="student">Student</option>
            <option value="business">Business</option>
            <option value="secured">Secured</option>
          </select></div>
        <div><label style={labelStyle}>Specific card product</label>
          <input type="text" style={inputStyle}
                 value={form.card_product_id}
                 onChange={(e) => update("card_product_id", e.target.value)} /></div>
        <div><label style={labelStyle}>What were they searching for?</label>
          <select style={inputStyle} value={form.query_intent}
                  onChange={(e) => update("query_intent", e.target.value as QueryIntent)}>
            <option value="compare">Comparing options</option>
            <option value="shop">Shopping for the best deal</option>
            <option value="apply">Ready to apply</option>
            <option value="research">Just researching</option>
            <option value="navigational">Looking for a brand</option>
          </select></div>
        <div><label style={labelStyle}>How likely are they to apply? (0–1)</label>
          <input type="number" min={0} max={1} step={0.01} style={inputStyle}
                 value={form.affinity_score}
                 onChange={(e) => update("affinity_score", parseFloat(e.target.value || "0"))} /></div>
        <div><label style={labelStyle}>Have they applied for a card before?</label>
          <select style={inputStyle} value={form.prior_applicant ? "yes" : "no"}
                  onChange={(e) => update("prior_applicant", e.target.value === "yes")}>
            <option value="no">No</option>
            <option value="yes">Yes</option>
          </select></div>
        <div><label style={labelStyle}>Income band (optional)</label>
          <select style={inputStyle} value={form.income_band_bucket}
                  onChange={(e) => update("income_band_bucket", e.target.value as IncomeBand)}>
            <option value="">Unknown</option>
            <option value="low">Low</option>
            <option value="mid">Mid</option>
            <option value="high">High</option>
          </select></div>
        <div><label style={labelStyle}>How crowded was the ad auction? (0–1)</label>
          <input type="number" min={0} max={1} step={0.01} style={inputStyle}
                 value={form.auction_pressure}
                 onChange={(e) => update("auction_pressure", parseFloat(e.target.value || "0"))} /></div>
        <div><label style={labelStyle}>Recent earnings: 14 / 60 days (£)</label>
          <div style={{ display: "flex", gap: 6 }}>
            <input type="number" step={0.01} style={inputStyle}
                   value={form.rpc_14d}
                   onChange={(e) => update("rpc_14d", parseFloat(e.target.value || "0"))} />
            <input type="number" step={0.01} style={inputStyle}
                   value={form.rpc_60d}
                   onChange={(e) => update("rpc_60d", parseFloat(e.target.value || "0"))} />
          </div>
        </div>
        <div><label style={labelStyle}>Repeat visits in the last 30 days</label>
          <input type="number" step={1} min={0} style={inputStyle}
                 value={form.visits_prev_30d}
                 onChange={(e) => update("visits_prev_30d", parseInt(e.target.value || "0"))} /></div>

        {/* Phoebe / GA4 behavioural features (PRD V2 §7.1) */}
        <div><label style={labelStyle}>Used a calculator on this visit?</label>
          <select style={inputStyle}
                  value={form.phoebe_calculator_used ? "yes" : "no"}
                  onChange={(e) => update("phoebe_calculator_used", e.target.value === "yes")}>
            <option value="no">No</option>
            <option value="yes">Yes</option>
          </select></div>
        <div><label style={labelStyle}>Guides read in the last 30 days</label>
          <input type="number" step={1} min={0} style={inputStyle}
                 value={form.phoebe_guides_read}
                 onChange={(e) => update("phoebe_guides_read", parseInt(e.target.value || "0"))} /></div>
        <div><label style={labelStyle}>Cards compared in the last 30 days</label>
          <input type="number" step={1} min={0} style={inputStyle}
                 value={form.phoebe_cards_compared}
                 onChange={(e) => update("phoebe_cards_compared", parseInt(e.target.value || "0"))} /></div>
        <div><label style={labelStyle}>Time engaged on the site (seconds)</label>
          <input type="number" step={1} min={0} style={inputStyle}
                 value={form.phoebe_session_engagement_s}
                 onChange={(e) => update("phoebe_session_engagement_s", parseFloat(e.target.value || "0"))} /></div>
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
                            fontWeight: 600 }}>What this click is worth</div>
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

      {result && (
        <BeforeAfterPanel
          predictedRpc={result.predicted_rpc}
          sessionSaved={sessionSaved}
        />
      )}

      {(busy || result) && (
        <div style={{
          marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--rule)",
        }}>
          <div style={{
            fontSize: 11, fontWeight: 700, color: "var(--muted)",
            letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8,
          }}>What's happening on Google Cloud right now</div>
          <PipelineTrace trace={trace} />
        </div>
      )}

      {result && result.attrs.length > 0 && (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--rule)" }}>
          <div style={{
            fontSize: 11, fontWeight: 700, color: "var(--muted)",
            letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 4,
          }}>Why the model said {fmtCurrency(result.predicted_rpc)}</div>
          <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>
            Each bar shows how much that single fact pushed the price
            <span style={{ color: "var(--green)", fontWeight: 700 }}> up</span> or
            <span style={{ color: "var(--red)", fontWeight: 700 }}> down</span>,
            starting from the model's baseline of <b>£{result.base_value.toFixed(2)}</b>.
          </div>
          <AttributionBars attrs={result.attrs} baseValue={result.base_value} />
        </div>
      )}
    </div>
  );
}

// ── Phoebe journey card ────────────────────────────────────────────────
// Animates a single user's session across 5 behavioural events. Each
// step mutates the Phoebe features and re-fires /v1/score; the predicted
// bid ticks up as the user's intent strengthens — the strategy doc's
// "Bouncer with a Crystal Ball" moment.

interface JourneyStep {
  label: string;
  detail: string;
  ts: string; // human "0:00" style
  delta: { // Phoebe state at this point in the session
    calculator_used: boolean;
    guides_read: number;
    cards_compared: number;
    session_engagement_s: number;
  };
}

const JOURNEY: JourneyStep[] = [
  {
    label: "Search lands",
    detail: "User Googles 'best cashback card UK'.",
    ts: "0:00",
    delta: { calculator_used: false, guides_read: 0, cards_compared: 0,
             session_engagement_s: 0 },
  },
  {
    label: "Opens the comparison page",
    detail: "Spends 30 seconds reading product summaries.",
    ts: "0:15",
    delta: { calculator_used: false, guides_read: 0, cards_compared: 0,
             session_engagement_s: 30 },
  },
  {
    label: "Tries the cashback calculator",
    detail: "Enters monthly spend, sees a £-back projection.",
    ts: "0:45",
    delta: { calculator_used: true, guides_read: 0, cards_compared: 0,
             session_engagement_s: 95 },
  },
  {
    label: "Reads two guides",
    detail: "Understands eligibility and credit-score impact.",
    ts: "1:30",
    delta: { calculator_used: true, guides_read: 2, cards_compared: 0,
             session_engagement_s: 220 },
  },
  {
    label: "Compares five cards side-by-side",
    detail: "Now ranking on annual fee + reward rate.",
    ts: "2:15",
    delta: { calculator_used: true, guides_read: 2, cards_compared: 5,
             session_engagement_s: 380 },
  },
  {
    label: "Clicks through to apply",
    detail: "The ad fires — your bidder needs an answer in under a second.",
    ts: "2:45",
    delta: { calculator_used: true, guides_read: 2, cards_compared: 5,
             session_engagement_s: 480 },
  },
];

interface JourneyResult {
  predictedRpc: number;
  source: string;
}

function PhoebeJourneyCard() {
  const [activeIdx, setActiveIdx] = useState<number>(-1);
  const [results, setResults] = useState<(JourneyResult | null)[]>(
    Array(JOURNEY.length).fill(null),
  );
  const [busy, setBusy] = useState(false);

  async function scoreAt(idx: number): Promise<JourneyResult | null> {
    const s = JOURNEY[idx]!;
    const payload = {
      ...DEFAULTS,
      click_id: `journey-${Date.now().toString(36)}-${idx}`,
      correlation_id: `journey-${Date.now().toString(36)}`,
      ad_creative_id: "journey-creative",
      landing_path: "/credit-cards/cashback",
      phoebe_calculator_used: s.delta.calculator_used,
      phoebe_guides_read: s.delta.guides_read,
      phoebe_cards_compared: s.delta.cards_compared,
      phoebe_session_engagement_s: s.delta.session_engagement_s,
    };
    try {
      const resp = await fetch("/score", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) return null;
      const j = await resp.json();
      return { predictedRpc: j.predicted_rpc, source: j.source };
    } catch {
      return null;
    }
  }

  async function play() {
    setBusy(true);
    setResults(Array(JOURNEY.length).fill(null));
    for (let i = 0; i < JOURNEY.length; i++) {
      setActiveIdx(i);
      const r = await scoreAt(i);
      setResults((prev) => {
        const next = [...prev];
        next[i] = r;
        return next;
      });
      // pause so the audience sees the bid tick up
      await new Promise((res) => setTimeout(res, 1100));
    }
    setActiveIdx(JOURNEY.length - 1);
    setBusy(false);
  }

  const firstRpc = results[0]?.predictedRpc ?? null;
  const lastRpc = results[JOURNEY.length - 1]?.predictedRpc ?? null;
  const lift = (firstRpc != null && lastRpc != null)
    ? lastRpc - firstRpc
    : null;

  return (
    <div className="card">
      <h3>Watch a single user's intent build up — and the bid follow it</h3>
      <div className="cardsub">
        Same person, same session. As they use the calculator, read guides,
        and compare cards, your bidder gets a richer read on their intent
        and prices the click accordingly. This is the "bouncer with a
        crystal ball" moment.
      </div>

      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        marginBottom: 14, paddingBottom: 10,
        borderBottom: "1px solid var(--rule)",
      }}>
        <button onClick={play} disabled={busy}
          style={{
            background: "var(--navy)", color: "#fff", border: 0,
            borderRadius: 6, padding: "8px 18px",
            fontSize: 12, fontWeight: 700, letterSpacing: "0.04em",
            cursor: busy ? "wait" : "pointer", opacity: busy ? 0.7 : 1,
          }}>{busy ? "Playing…" : "▶ Play the journey"}</button>
        {firstRpc != null && (
          <span style={{ fontSize: 12, color: "var(--muted)" }}>
            Started bidding at <b style={{ color: "var(--navy)" }}>
              {fmtCurrency(firstRpc)}
            </b>
          </span>
        )}
        {lift != null && (
          <span style={{
            marginLeft: "auto", padding: "4px 10px",
            background: lift >= 0 ? "var(--green-50)" : "var(--accent-50)",
            color: lift >= 0 ? "var(--green)" : "var(--accent)",
            borderRadius: 999, fontSize: 12, fontWeight: 700,
          }}>
            {lift >= 0 ? "▲" : "▼"} {fmtCurrency(Math.abs(lift))} across the session
          </span>
        )}
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: `repeat(${JOURNEY.length}, 1fr)`,
        gap: 8,
      }}>
        {JOURNEY.map((s, i) => {
          const active = i === activeIdx;
          const settled = results[i] != null;
          return (
            <div key={i} style={{
              padding: "10px 12px", borderRadius: 8,
              border: `1px solid ${active ? "var(--navy)" : "var(--rule)"}`,
              background: active ? "var(--teal-50)"
                : settled ? "#fff" : "#fafafa",
              opacity: settled || active ? 1 : 0.55,
              transition: "all 0.25s ease",
              minHeight: 130,
              display: "flex", flexDirection: "column", gap: 4,
            }}>
              <div style={{
                fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
                color: "var(--muted)", textTransform: "uppercase",
              }}>{s.ts}</div>
              <div style={{
                fontSize: 12, fontWeight: 700, color: "var(--navy)",
              }}>{s.label}</div>
              <div style={{
                fontSize: 11, color: "var(--muted)", flex: 1,
                lineHeight: 1.35,
              }}>{s.detail}</div>
              {results[i] && (
                <div style={{
                  marginTop: 4, paddingTop: 4,
                  borderTop: "1px dashed var(--rule)",
                  fontSize: 13, fontWeight: 700, color: "var(--teal)",
                  fontVariantNumeric: "tabular-nums",
                }}>
                  {fmtCurrency(results[i]!.predictedRpc)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Before/After hero panel ────────────────────────────────────────────
// Same click, two worlds: the flat-tCPA target the old bidder would have
// paid, and the value-based bid this engine would place. The session
// counter accumulates the absolute gap across every prediction the user
// has fired so far this page load.
function BeforeAfterPanel({ predictedRpc, sessionSaved }: {
  predictedRpc: number;
  sessionSaved: { totalGbp: number; clicks: number };
}) {
  const valueBid = predictedRpc * BID_EFFICIENCY;
  const delta = valueBid - TCPA_FLAT_BID;
  const verdict = delta >= 0
    ? "Higher-value click — the old bidder would have under-bid and lost it"
    : "Lower-value click — the old bidder would have over-paid";
  const accent = delta >= 0 ? "var(--green)" : "var(--accent)";

  const colStyle: React.CSSProperties = {
    flex: 1,
    padding: "12px 14px",
    borderRadius: 8,
    background: "#fff",
    border: "1px solid var(--rule)",
    minWidth: 0,
  };
  const labelStyle: React.CSSProperties = {
    fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
    textTransform: "uppercase", color: "var(--muted)", marginBottom: 6,
  };
  const valueStyle: React.CSSProperties = {
    fontSize: 28, fontWeight: 700, letterSpacing: "-0.01em",
    color: "var(--navy)", fontVariantNumeric: "tabular-nums",
  };

  return (
    <div style={{
      marginTop: 14, paddingTop: 12,
      borderTop: "1px solid var(--rule)",
    }}>
      <div style={{
        fontSize: 11, fontWeight: 700, color: "var(--muted)",
        letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8,
      }}>The same click, in two worlds</div>

      <div style={{
        display: "flex", gap: 10, flexWrap: "wrap",
        alignItems: "stretch",
      }}>
        <div style={colStyle}>
          <div style={labelStyle}>Old world · Flat target-CPA</div>
          <div style={{ ...valueStyle, color: "var(--muted)" }}>
            {fmtCurrency(TCPA_FLAT_BID)}
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            Same £ for every click — no idea if it's a whale or a minnow.
          </div>
        </div>

        <div style={{ ...colStyle, borderColor: accent, background: "var(--teal-50)" }}>
          <div style={labelStyle}>New world · Value-based bid</div>
          <div style={{ ...valueStyle, color: accent }}>
            {fmtCurrency(valueBid)}
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
            {Math.round(BID_EFFICIENCY * 100)}% of predicted earnings — keeps the
            margin on the bid that actually wins.
          </div>
        </div>

        <div style={{ ...colStyle, background: "var(--navy)", color: "#fff",
                      borderColor: "var(--navy)" }}>
          <div style={{ ...labelStyle, color: "rgba(255,255,255,0.7)" }}>
            Difference on this click
          </div>
          <div style={{ ...valueStyle, color: "#fff" }}>
            {delta >= 0 ? "+" : ""}{fmtCurrency(delta)}
          </div>
          <div style={{ fontSize: 11, color: "rgba(255,255,255,0.75)", marginTop: 4 }}>
            {verdict}.
          </div>
        </div>
      </div>

      {sessionSaved.clicks > 1 && (
        <div style={{
          marginTop: 10, padding: "8px 12px", borderRadius: 6,
          background: "var(--green-50)",
          display: "flex", alignItems: "center", gap: 10,
          fontSize: 12,
        }}>
          <span style={{ color: "var(--green)", fontWeight: 700 }}>
            Across this demo session
          </span>
          <span style={{ color: "var(--slate)" }}>
            {fmtInt(sessionSaved.clicks)} clicks scored — total better-priced
            value vs flat tCPA: {" "}
            <b style={{ color: "var(--navy)",
                        fontVariantNumeric: "tabular-nums" }}>
              {fmtCurrency(sessionSaved.totalGbp)}
            </b>
          </span>
          <span style={{ marginLeft: "auto", color: "var(--muted)" }}>
            scale that across MSM's real Credit Cards volume — that's the
            commercial case.
          </span>
        </div>
      )}
    </div>
  );
}

function PipelineTrace({ trace }: { trace: TraceStep[] }) {
  return (
    <ol style={{ margin: 0, padding: 0, listStyle: "none",
                 display: "flex", flexDirection: "column", gap: 6 }}>
      {trace.map((step, i) => {
        const colour =
          step.status === "done"    ? "var(--green)"
          : step.status === "active"? "var(--accent)"
          : step.status === "skipped"? "var(--muted)"
          : "var(--rule)";
        const icon =
          step.status === "done"   ? "✓"
          : step.status === "active"? "•"
          : step.status === "skipped"? "—"
          : "○";
        const bold = step.status === "done" || step.status === "active";
        return (
          <li key={i} style={{
            display: "grid",
            gridTemplateColumns: "22px 1fr 70px",
            alignItems: "start",
            opacity: step.status === "pending" ? 0.45 : 1,
            transition: "opacity 0.2s",
          }}>
            <span style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 18, height: 18, borderRadius: 999,
              background: step.status === "done" ? "var(--green-50)"
                        : step.status === "active" ? "var(--accent-50)"
                        : step.status === "skipped" ? "#f1f3f7"
                        : "transparent",
              color: colour,
              fontSize: 11, fontWeight: 700,
              border: step.status === "pending" ? "1px dashed var(--rule)" : "none",
            }}>{icon}</span>
            <div>
              <div style={{ fontSize: 12, color: "var(--navy)", fontWeight: bold ? 700 : 500 }}>
                {step.label}
                {step.status === "active" && (
                  <span style={{ color: "var(--accent)", marginLeft: 6, fontWeight: 600 }}>
                    …working
                  </span>
                )}
              </div>
              <div style={{ fontSize: 11, color: "var(--muted)" }}>{step.detail}</div>
            </div>
            <span style={{
              textAlign: "right", fontSize: 11, color: "var(--muted)",
              fontVariantNumeric: "tabular-nums",
            }}>
              {step.ms !== undefined ? `${step.ms} ms`
                : step.status === "skipped" ? "skipped"
                : ""}
            </span>
          </li>
        );
      })}
    </ol>
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
