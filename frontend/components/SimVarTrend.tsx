"use client";
import React from "react";
import type { SimulationBlock } from "@/lib/types";
import { Card, EmptyNote, Pill, SectionHeader } from "./ui";
import { LineChart } from "./Charts";
import { fmtMoney } from "@/lib/format";

// Point-in-time Simulation VaR over the latest valid as-of dates (calculated, not
// stored). Supports management wording like "VaR decreased / steady / increased".
export function SimVarTrend({ simulation }: { simulation: SimulationBlock }) {
  const trend = simulation?.var_trend || [];
  const unit = simulation?.unit || "USD";

  if (!simulation?.available || trend.length === 0) {
    return (
      <Card className="p-5">
        <SectionHeader title="Simulation VaR Trend" />
        <EmptyNote>Not enough history to build a VaR trend.</EmptyNote>
      </Card>
    );
  }

  function trendPill(t: string | null) {
    if (!t) return <span className="text-ink-muted">—</span>;
    const tone = t === "Increased" ? "warn" : t === "Decreased" ? "accent" : "default";
    return <Pill tone={tone as any}>{t}</Pill>;
  }

  return (
    <Card className="p-5">
      <SectionHeader
        title="Simulation VaR Trend"
        subtitle={`Point-in-time VaR (each as-of date uses only data up to that date). Trend threshold ±${simulation.trend_threshold_pct ?? 5}%.`}
        right={
          simulation.var_trend_classification ? (
            <span className="text-xs text-ink-muted">
              Current vs previous: {trendPill(simulation.var_trend_classification)}
            </span>
          ) : null
        }
      />

      <div className="mb-4 rounded-md border border-line p-3">
        <LineChart points={trend.map((p) => ({ x: p.as_of_date, y: p.simulation_var }))} />
      </div>

      <div className="overflow-x-auto scroll-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
              <th className="py-2 pr-4 font-semibold">As-of Date</th>
              <th className="py-2 pr-4 text-right font-semibold">Simulation VaR</th>
              <th className="py-2 pr-4 text-right font-semibold">VaR Variance</th>
              <th className="py-2 pr-4 text-right font-semibold">VaR Variance %</th>
              <th className="py-2 pr-4 font-semibold">Trend</th>
            </tr>
          </thead>
          <tbody>
            {trend.map((p, i) => (
              <tr key={i} className="border-b border-line/60">
                <td className="py-1.5 pr-4 text-ink-muted">{p.as_of_date}</td>
                <td className="py-1.5 pr-4 text-right tabular font-medium">{fmtMoney(p.simulation_var, unit)}</td>
                <td className={`py-1.5 pr-4 text-right tabular ${p.var_variance != null && p.var_variance < 0 ? "text-positive" : p.var_variance != null && p.var_variance > 0 ? "text-negative" : "text-ink-muted"}`}>
                  {p.var_variance == null ? "—" : `${p.var_variance > 0 ? "+" : ""}${fmtMoney(p.var_variance, unit)}`}
                </td>
                <td className="py-1.5 pr-4 text-right tabular text-ink-muted">
                  {p.var_variance_pct == null ? "N/A" : `${p.var_variance_pct}%`}
                </td>
                <td className="py-1.5 pr-4">{trendPill(p.trend)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
