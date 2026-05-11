// Hand-rolled SVG charts — keep the dependency footprint to React only.
import { useMemo } from "react";
import { fmtCurrency, fmtDateOnly } from "./format";

const NAVY = "#0b1f3a";
const TEAL = "#0f6e7a";
const ACCENT = "#d97306";
const MUTED = "#6b7380";
const RULE = "#e3e6ec";

interface DailyPoint {
  dayMs: number;
  predicted: number;  // mean predicted RPC
  realized: number;   // mean realized RPC
  count: number;
}

export function DailyComparisonChart({ data }: { data: DailyPoint[] }) {
  const width = 640;
  const height = 240;
  const padL = 56, padR = 16, padT = 16, padB = 28;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const layout = useMemo(() => {
    if (data.length === 0) return null;
    const ys = data.flatMap(d => [d.predicted, d.realized]);
    const yMax = Math.max(1, Math.ceil(Math.max(...ys) * 1.15 * 10) / 10);
    const yMin = 0;
    const xStep = data.length > 1 ? plotW / (data.length - 1) : 0;
    const x = (i: number) => padL + i * xStep;
    const y = (v: number) => padT + plotH - ((v - yMin) / (yMax - yMin)) * plotH;
    return { yMax, x, y };
  }, [data, plotW, plotH, padL, padT]);

  if (!layout) return <div className="empty">No data in window.</div>;

  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => (layout.yMax / ticks) * i);

  const pathFrom = (key: "predicted" | "realized") =>
    data.map((d, i) => `${i === 0 ? "M" : "L"} ${layout.x(i)} ${layout.y(d[key])}`).join(" ");

  const xLabelEvery = Math.max(1, Math.ceil(data.length / 6));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img"
         aria-label="Daily predicted vs realized RPC">
      {/* gridlines */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={width - padR} y1={layout.y(t)} y2={layout.y(t)}
                stroke={RULE} strokeWidth={1} shapeRendering="crispEdges" />
          <text x={padL - 8} y={layout.y(t) + 3} fontSize={10} fill={MUTED} textAnchor="end">
            {fmtCurrency(t)}
          </text>
        </g>
      ))}
      {/* x labels */}
      {data.map((d, i) => i % xLabelEvery === 0 ? (
        <text key={i} x={layout.x(i)} y={height - 8} fontSize={10} fill={MUTED} textAnchor="middle">
          {fmtDateOnly(d.dayMs)}
        </text>
      ) : null)}
      {/* lines */}
      <path d={pathFrom("predicted")} fill="none" stroke={TEAL} strokeWidth={2} />
      <path d={pathFrom("realized")}  fill="none" stroke={ACCENT} strokeWidth={2} />
      {/* points */}
      {data.map((d, i) => (
        <g key={i}>
          <circle cx={layout.x(i)} cy={layout.y(d.predicted)} r={3} fill={TEAL} />
          <circle cx={layout.x(i)} cy={layout.y(d.realized)}  r={3} fill={ACCENT} />
        </g>
      ))}
    </svg>
  );
}

interface SourceSlice {
  label: string;
  value: number;
  color: string;
}

export function SourceDonut({ slices }: { slices: SourceSlice[] }) {
  const size = 200;
  const r = 70;
  const cx = size / 2;
  const cy = size / 2;
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  let acc = 0;
  const arcs = slices.map(s => {
    const start = acc / total;
    acc += s.value;
    const end = acc / total;
    return { ...s, start, end };
  });

  function arcPath(start: number, end: number) {
    const a0 = start * 2 * Math.PI - Math.PI / 2;
    const a1 = end   * 2 * Math.PI - Math.PI / 2;
    const x0 = cx + r * Math.cos(a0);
    const y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1);
    const y1 = cy + r * Math.sin(a1);
    const large = end - start > 0.5 ? 1 : 0;
    return `M ${cx} ${cy} L ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} Z`;
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img"
           aria-label="Prediction source breakdown">
        {arcs.map((a, i) => (
          <path key={i} d={arcPath(a.start, a.end)} fill={a.color} />
        ))}
        <circle cx={cx} cy={cy} r={r * 0.55} fill="#fff" />
        <text x={cx} y={cy - 4} fontSize={11} fill={MUTED} textAnchor="middle">Total</text>
        <text x={cx} y={cy + 14} fontSize={18} fill={NAVY} textAnchor="middle" fontWeight={700}>
          {total}
        </text>
      </svg>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 140 }}>
        {arcs.map((a, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", fontSize: 12 }}>
            <span style={{ display: "inline-block", width: 10, height: 10, background: a.color,
                           borderRadius: 2, marginRight: 8 }} />
            <span style={{ color: MUTED, marginRight: "auto" }}>{a.label}</span>
            <span style={{ color: NAVY, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
              {a.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export interface ResidualPoint { value: number; }
export function ResidualHistogram({ values, bins = 11 }: { values: number[]; bins?: number }) {
  const width = 320;
  const height = 200;
  const padL = 36, padR = 12, padT = 8, padB = 26;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  if (values.length === 0) {
    return <div className="empty" style={{ padding: 16 }}>No reconciled values.</div>;
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const abs = Math.max(Math.abs(min), Math.abs(max), 0.5);
  const lo = -abs, hi = abs;
  const step = (hi - lo) / bins;
  const counts = Array(bins).fill(0) as number[];
  for (const v of values) {
    const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - lo) / step)));
    counts[idx] = (counts[idx] ?? 0) + 1;
  }
  const maxC = Math.max(1, ...counts);
  const barW = plotW / bins;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img"
         aria-label="Residual distribution">
      {/* zero line */}
      <line x1={padL + plotW / 2} x2={padL + plotW / 2}
            y1={padT} y2={padT + plotH}
            stroke={RULE} strokeDasharray="2 3" />
      {counts.map((c, i) => {
        const h = (c / maxC) * plotH;
        const x = padL + i * barW + 1;
        const y = padT + plotH - h;
        const center = lo + step * (i + 0.5);
        const fill = center < -0.05 ? "#b9341d" : center > 0.05 ? "#1f8a4f" : MUTED;
        return <rect key={i} x={x} y={y} width={barW - 2} height={h} fill={fill} opacity={0.85} rx={1.5} />;
      })}
      {/* x-axis labels */}
      <text x={padL} y={height - 8} fontSize={10} fill={MUTED} textAnchor="start">
        {fmtCurrency(lo)}
      </text>
      <text x={padL + plotW / 2} y={height - 8} fontSize={10} fill={MUTED} textAnchor="middle">
        £0.00
      </text>
      <text x={padL + plotW} y={height - 8} fontSize={10} fill={MUTED} textAnchor="end">
        {fmtCurrency(hi)}
      </text>
    </svg>
  );
}
