"use client";
import React from "react";
import { Card, EmptyNote, InfoDot, SectionHeader } from "./ui";
import { BarChart } from "./Charts";
import { RiskFactorTable } from "./RiskFactorTable";
import { ScenarioAnalysis } from "./ScenarioAnalysis";
import { fmtMoney, fmtNumber } from "@/lib/format";

// Renders only the dimensions the user selected. Each section is data-supported and
// labelled precisely (e.g. "Market Value by Asset Class", never "VaR Contribution").
export function DimensionAnalysis({
  dimensions,
  analysis,
  stressPnl,
  onLineage,
}: {
  dimensions: string[];
  analysis: Record<string, any>;
  stressPnl: Record<string, any>;
  onLineage: (key: string) => void;
}) {
  if (!dimensions.length) return null;

  return (
    <Card className="p-5">
      <SectionHeader
        title="Dimension Analysis"
        subtitle="Only the dimensions you selected are shown, each derived through actual workbook relationships."
      />
      <div className="space-y-6">
        {dimensions.map((dim) => {
          const payload = analysis[dim];
          if (!payload) return null;
          return (
            <div key={dim}>
              <div className="mb-2 flex items-center gap-1.5">
                <h3 className="text-sm font-semibold text-ink">{dim}</h3>
                <InfoDot onClick={() => onLineage(lineageKey(dim))} />
              </div>
              {renderDimension(dim, payload, stressPnl, onLineage)}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function lineageKey(dim: string): string {
  if (dim === "Risk Factor") return "Associated Risk Factors";
  if (dim === "Scenario") return "Scenario";
  return dim;
}

function renderDimension(dim: string, payload: any, stressPnl: any, onLineage: (k: string) => void) {
  if (["Asset Class", "Desk", "Book", "Instrument"].includes(dim)) {
    const rows: any[] = payload.rows || [];
    if (!rows.length) return <EmptyNote>No data for this dimension.</EmptyNote>;
    const barData = rows.map((r) => ({
      label: r.assetClass || r.name || r.instrumentName || r.id,
      value: r.market_value_bcy,
    }));
    return (
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-line p-3">
          <p className="mb-2 text-xs font-semibold text-ink-muted">{payload.label}</p>
          <BarChart data={barData} height={Math.max(140, rows.length * 32)} />
        </div>
        <div className="overflow-x-auto scroll-thin rounded-md border border-line p-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="py-1.5 pr-3 font-semibold">Name</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Positions</th>
                {dim === "Asset Class" && <th className="py-1.5 pr-3 text-right font-semibold">Instruments</th>}
                <th className="py-1.5 pr-3 text-right font-semibold">Market Value</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-line/60">
                  <td className="py-1.5 pr-3 font-medium text-ink">{r.assetClass || r.name || r.instrumentName || r.id}</td>
                  <td className="py-1.5 pr-3 text-right tabular">{fmtNumber(r.position_count)}</td>
                  {dim === "Asset Class" && <td className="py-1.5 pr-3 text-right tabular">{fmtNumber(r.instrument_count)}</td>}
                  <td className={`py-1.5 pr-3 text-right tabular ${r.market_value_bcy < 0 ? "text-negative" : "text-positive"}`}>
                    {fmtMoney(r.market_value_bcy)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (dim === "Business") {
    const rows: any[] = payload.rows || [];
    return (
      <div className="space-y-2">
        <p className="text-xs font-semibold text-ink-muted">{payload.label}</p>
        {rows.map((r) => (
          <div key={r.businessUnitId} className="rounded-md border border-line p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-ink">{r.businessUnit}</span>
              <span className="text-xs text-ink-muted">{r.metric_count} metric(s)</span>
            </div>
            {r.metrics?.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {r.metrics.map((m: any) => (
                  <span key={m.riskMetricId} className="rounded border border-line bg-slate-50 px-2 py-1 text-xs tabular">
                    {m.riskMetricId}: <span className={m.latest_var < 0 ? "text-negative" : "text-positive"}>{fmtMoney(m.latest_var)}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  if (dim === "Risk Factor") {
    return <RiskFactorTable riskFactors={payload.rows || []} onLineage={() => onLineage("Associated Risk Factors")} />;
  }

  if (dim === "Scenario") {
    return <ScenarioAnalysis scenarioAnalysis={payload} stressPnl={stressPnl} embedded />;
  }

  return <EmptyNote>Unsupported dimension.</EmptyNote>;
}
