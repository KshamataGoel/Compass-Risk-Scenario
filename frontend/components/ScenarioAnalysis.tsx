"use client";
import React from "react";
import { Card, EmptyNote, Pill, SectionHeader } from "./ui";
import { BarChart } from "./Charts";
import { fmtMoney, signColor } from "@/lib/format";

// Renders the scenario dimension: explicit stress shocks + scenario P&L (where present).
export function ScenarioAnalysis({
  scenarioAnalysis,
  stressPnl,
  embedded = false,
}: {
  scenarioAnalysis: Record<string, any>;
  stressPnl?: Record<string, any>;
  embedded?: boolean;
}) {
  const scenarios: any[] = scenarioAnalysis?.scenarios || [];
  const body = (
    <>
      {stressPnl?.available && (
        <div className="mb-4 rounded-md border border-line bg-slate-50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Total Stress Scenario P&amp;L</span>
            <Pill>Not VaR</Pill>
          </div>
          <div className={`mt-1 text-xl font-semibold tabular ${signColor(stressPnl.total_pnl)}`}>
            {fmtMoney(stressPnl.total_pnl, stressPnl.currency)}
          </div>
          {stressPnl.by_component?.length > 0 && (
            <div className="mt-3">
              <BarChart data={stressPnl.by_component.map((c: any) => ({ label: c.key, value: c.value }))} height={150} />
            </div>
          )}
        </div>
      )}

      <div className="space-y-3">
        {scenarios.map((s) => (
          <div key={s.scenarioSetId} className="rounded-md border border-line p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <span className="text-sm font-semibold text-ink">{s.scenarioSetName}</span>
                <span className="ml-2 text-xs text-ink-muted">{s.scenarioType} · {s.scenarioDate}</span>
              </div>
              {s.scenario_pnl?.available ? (
                <span className={`text-sm font-semibold tabular ${signColor(s.scenario_pnl.total_pnl)}`}>
                  {fmtMoney(s.scenario_pnl.total_pnl)}
                </span>
              ) : (
                <Pill tone="warn">P&amp;L not available from current data model</Pill>
              )}
            </div>
            <div className="mt-2 overflow-x-auto scroll-thin">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left uppercase tracking-wide text-ink-muted">
                    <th className="py-1 pr-3 font-semibold">Risk Factor</th>
                    <th className="py-1 pr-3 font-semibold">Shock Type</th>
                    <th className="py-1 pr-3 text-right font-semibold">Value</th>
                    <th className="py-1 pr-3 font-semibold">Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {s.shocks.map((sh: any, i: number) => (
                    <tr key={i} className="border-t border-line/50">
                      <td className="py-1 pr-3 text-ink">{sh.riskFactorName}</td>
                      <td className="py-1 pr-3 text-ink-muted">{sh.shockType}</td>
                      <td className="py-1 pr-3 text-right tabular">{sh.shockValue}</td>
                      <td className="py-1 pr-3 text-ink-muted">{sh.shockUnit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </>
  );

  if (embedded) return scenarios.length ? body : <EmptyNote>No scenario data.</EmptyNote>;

  return (
    <Card className="p-5">
      <SectionHeader
        title="Scenario Analysis"
        subtitle="Explicit stress shocks (scenario_mr → risk_factor_shock). Distinct from historical-simulation movements."
      />
      {scenarios.length ? body : <EmptyNote>No scenario data.</EmptyNote>}
    </Card>
  );
}
