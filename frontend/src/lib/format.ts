export function fmt(v: number, digits = 2): string {
  if (v === undefined || v === null) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtPct(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export function fmtK(v: number): string {
  if (Math.abs(v) >= 1e12) return `${(v / 1e12).toFixed(2)}T`;
  if (Math.abs(v) >= 1e9)  return `${(v / 1e9).toFixed(2)}B`;
  if (Math.abs(v) >= 1e6)  return `${(v / 1e6).toFixed(2)}M`;
  if (Math.abs(v) >= 1e3)  return `${(v / 1e3).toFixed(2)}K`;
  return String(v);
}
