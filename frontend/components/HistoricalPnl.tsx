"use client";
import React from "react";
import type { SimulationBlock } from "@/lib/types";
import { Card, EmptyNote, InfoDot, Pill, SectionHeader } from "./ui";
import { BarChart, LineChart } from "./Charts";
import { fmtMoney, fmtNumber } from "@/lib/format";

// Real-time Historical Simulation output: portfolio value history, the P&L
// distribution, and the VaR loss point — all calculated, none stored.
export function HistoricalPnl({
  simulation,
  utilisation,
  onLineage,
}: {
  simulation: SimulationBlock;
  utilisation: Record<string, any>;
  onLineage: () => void;
}) {
  if (!simulation?.available) {
    return (
      <Card className="p-5">
        <SectionHeader title="Historical Simulation P&L" />
        <EmptyNote>{simulation?.message || "Simulation VaR could not be calculated."}</EmptyNote>
      </Card>
    );
  }

  const unit = simulation.unit || "USD";
  const pnl = simulation.pnl_distribution || [];
  const history = simulation.portfolio_history_window || [];
  const tail = simulation.tail_period || null;   // the selected loss observation (null if VaR = 0)
  const trendClass = simulation.var_trend_classification || null;
  const trendTone = trendClass === "Increased" ? "text-negative" : trendClass === "Decreased" ? "text-positive" : "text-ink";

  const kpis = [
    { label: "Simulation VaR", value: fmtMoney(simulation.simulation_var, unit), tone: "text-ink" },
    {
      label: "Previous Simulation VaR",
      value: simulation.previous_available ? fmtMoney(simulation.previous_simulation_var ?? null, unit) : "UNAVAILABLE",
      tone: simulation.previous_available ? "text-ink" : "text-warn",
    },
    {
      label: "VaR Variance",
      value: simulation.var_variance === null || simulation.var_variance === undefined ? "—" : fmtMoney(simulation.var_variance, unit),
      tone: "text-ink",
    },
    {
      label: "VaR Variance %",
      value: simulation.var_variance_pct === null || simulation.var_variance_pct === undefined ? "N/A" : `${simulation.var_variance_pct}%`,
      tone: "text-ink",
    },
    { label: "VaR Trend", value: trendClass || "—", tone: trendTone },
    { label: "Utilisation", value: utilisation?.available ? `${utilisation.utilisation_pct}%` : "—", tone: "text-accent" },
  ];

  return (
    <Card className="p-5">
      <SectionHeader
        title="Historical Simulation P&L"
        subtitle={`Calculated: ${simulation.observation_count} P&L observations (lookback N=${simulation.lookback_days}) · ${simulation.horizon_days}-day horizon · ${simulation.confidence_level}% confidence (tail ${(simulation.tail_probability ?? 0)}).`}
        right={<span className="text-xs text-ink-muted">Lineage <InfoDot onClick={onLineage} /></span>}
      />

      <div className="mb-4 flex flex-wrap gap-3">
        {kpis.map((k) => (
          <div key={k.label} className="rounded-md border border-line bg-slate-50 px-3 py-2">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-muted">{k.label}</div>
            <div className={`text-sm font-semibold tabular ${k.tone}`}>{k.value}</div>
          </div>
        ))}
        <div className="rounded-md border border-line bg-slate-50 px-3 py-2">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-muted">VaR tail P&L</div>
          <div className="text-sm font-semibold tabular text-negative">
            {tail ? `${fmtMoney(tail.tail_pnl, unit)}` : "None (VaR = 0)"}
          </div>
          {tail && <div className="text-[10px] text-ink-muted">{tail.start_date} → {tail.end_date}</div>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-line p-3">
          <p className="mb-2 text-xs font-semibold text-ink-muted">Portfolio Value by Date (lookback window)</p>
          <LineChart points={history.map((h) => ({ x: h.date, y: h.portfolio_value }))} />
        </div>
        <div className="rounded-md border border-line p-3">
          <p className="mb-2 text-xs font-semibold text-ink-muted">Historical P&L by end date (VaR = worst tail)</p>
          <BarChart data={pnl.map((p) => ({ label: p.end_date, value: p.historical_pnl }))} currency={unit} height={Math.max(140, pnl.length * 30)} />
        </div>
      </div>

      <div className="mt-4">
        <p className="mb-2 text-xs font-semibold text-ink-muted">P&L Distribution (for validation)</p>
        <div className="overflow-x-auto scroll-thin">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="py-2 pr-4 font-semibold">Start Date</th>
                <th className="py-2 pr-4 font-semibold">End Date</th>
                <th className="py-2 pr-4 text-right font-semibold">Starting Value</th>
                <th className="py-2 pr-4 text-right font-semibold">Ending Value</th>
                <th className="py-2 pr-4 text-right font-semibold">Historical P&L</th>
              </tr>
            </thead>
            <tbody>
              {[...pnl]
                .sort((a, b) => a.historical_pnl - b.historical_pnl)
                .map((r, i) => {
                  // Mark only the loss observation the VaR selected (never a gain).
                  const isTail = !!tail && r.start_date === tail.start_date && r.end_date === tail.end_date;
                  return (
                    <tr key={i} className={`border-b border-line/60 ${isTail ? "bg-negative/5" : ""}`}>
                      <td className="py-1.5 pr-4 text-ink-muted">{r.start_date}</td>
                      <td className="py-1.5 pr-4 text-ink-muted">{r.end_date}</td>
                      <td className="py-1.5 pr-4 text-right tabular">{fmtNumber(r.starting_portfolio_value)}</td>
                      <td className="py-1.5 pr-4 text-right tabular">{fmtNumber(r.ending_portfolio_value)}</td>
                      <td className={`py-1.5 pr-4 text-right tabular font-medium ${r.historical_pnl < 0 ? "text-negative" : "text-positive"}`}>
                        {r.historical_pnl > 0 ? "+" : ""}{fmtNumber(r.historical_pnl)}
                        {isTail && <Pill tone="warn">VaR point</Pill>}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}
