"use client";
import React from "react";
import { Card, Pill, SectionHeader } from "./ui";

export function SimulationParameters({ params }: { params: Record<string, any> }) {
  const horizon = params.forward_horizon_days ?? params.forward_days;
  const items: { label: string; value: string }[] = [
    { label: "Portfolio Type", value: params.portfolio_type },
    { label: "Risk Horizon", value: horizon === 1 ? "1 Day" : `${horizon} Days` },
    { label: "Historical P&L Lookback", value: `${params.lookback_days} P&L Observations` },
    { label: "Confidence", value: params.confidence_level ? `${params.confidence_level}%` : "—" },
    { label: "Methodology", value: params.methodology || "—" },
    { label: "As-of Date", value: params.as_of_date || "—" },
  ];
  return (
    <Card className="p-5">
      <SectionHeader title="Simulation Parameters" subtitle="The configuration deterministically resolved from the workbook." />
      <div className="flex flex-wrap gap-2">
        {items.map((it) => (
          <div key={it.label} className="rounded-md border border-line bg-slate-50 px-3 py-2">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-muted">{it.label}</div>
            <div className="text-sm font-semibold text-ink">{it.value}</div>
          </div>
        ))}
      </div>
      {Array.isArray(params.dimensions) && params.dimensions.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-ink-muted">Commentary dimensions:</span>
          {params.dimensions.map((d: string) => (
            <Pill key={d} tone="accent">{d}</Pill>
          ))}
        </div>
      )}
    </Card>
  );
}
