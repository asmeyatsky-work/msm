export const gbp = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "GBP",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const pct = new Intl.NumberFormat("en-GB", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export const intFmt = new Intl.NumberFormat("en-GB");

export function fmtCurrency(n: number): string {
  return gbp.format(n);
}

export function fmtPercent(n: number): string {
  return pct.format(n);
}

export function fmtInt(n: number): string {
  return intFmt.format(n);
}

export function fmtDate(ms: number): string {
  return new Date(ms).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtDateOnly(ms: number): string {
  return new Date(ms).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
  });
}

export function shorten(s: string, n = 14): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}
