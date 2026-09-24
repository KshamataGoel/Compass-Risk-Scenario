// Presentation helpers. These format numbers already produced by the backend;
// they never derive or alter risk figures.

export function fmtMoney(v: number | null | undefined, currency = "USD"): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  let scaled = v;
  let suffix = "";
  if (abs >= 1_000_000_000) { scaled = v / 1_000_000_000; suffix = "bn"; }
  else if (abs >= 1_000_000) { scaled = v / 1_000_000; suffix = "m"; }
  else if (abs >= 1_000) { scaled = v / 1_000; suffix = "k"; }
  const sign = v < 0 ? "-" : "";
  const body = suffix ? Math.abs(scaled).toFixed(1) : Math.abs(scaled).toLocaleString();
  const symbol = currency === "USD" ? "$" : "";
  return `${sign}${symbol}${body}${suffix}`;
}

export function fmtNumber(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v.toFixed(digits)}%`;
}

export function fmtMovement(m: { basis: string; value: number } | null | undefined): string {
  if (!m || m.value === null || m.value === undefined) return "—";
  const sign = m.value > 0 ? "+" : "";
  if (m.basis === "bps") return `${sign}${m.value.toFixed(1)} bps`;
  return `${sign}${m.value.toFixed(3)}%`;
}

export function statusColor(status: string): string {
  switch (status) {
    case "STORED": return "bg-accent/10 text-accent border-accent/20";
    case "CALCULATED": return "bg-positive/10 text-positive border-positive/20";
    case "REFERENCE": return "bg-slate-100 text-ink-muted border-slate-300";
    case "UNAVAILABLE": return "bg-warn/10 text-warn border-warn/20";
    default: return "bg-slate-100 text-slate-600 border-slate-200";
  }
}

export function signColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-ink";
  return v < 0 ? "text-negative" : "text-positive";
}
