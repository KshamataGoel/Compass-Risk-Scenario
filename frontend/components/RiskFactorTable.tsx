"use client";
import React from "react";
import type { RiskFactor } from "@/lib/types";
import { Card, InfoDot, SectionHeader } from "./ui";
import { fmtMovement, fmtNumber } from "@/lib/format";

export function RiskFactorTable({
  riskFactors,
  onLineage,
}: {
  riskFactors: RiskFactor[];
  onLineage: () => void;
}) {
  return (
    <Card className="p-5">
      <SectionHeader
        title="Associated Risk Factors"
        subtitle="Exposure/association via instrument_risk_factor_map — not a contribution ranking."
        right={<span className="text-xs text-ink-muted">Lineage <InfoDot onClick={onLineage} /></span>}
      />
      <div className="overflow-x-auto scroll-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
              <th className="py-2 pr-3 font-semibold">Risk Factor</th>
              <th className="py-2 pr-3 font-semibold">Type</th>
              <th className="py-2 pr-3 font-semibold">Subtype</th>
              <th className="py-2 pr-3 font-semibold">Tenor</th>
              <th className="py-2 pr-3 font-semibold">Ccy</th>
              <th className="py-2 pr-3 text-right font-semibold">Latest</th>
              <th className="py-2 pr-3 text-right font-semibold">Min</th>
              <th className="py-2 pr-3 text-right font-semibold">Max</th>
              <th className="py-2 pr-3 text-right font-semibold">1-Day Move</th>
            </tr>
          </thead>
          <tbody>
            {riskFactors.map((rf) => (
              <tr key={rf.riskFactorId} className="border-b border-line/60">
                <td className="py-2 pr-3 font-medium text-ink">{rf.riskFactorName}</td>
                <td className="py-2 pr-3 text-ink-muted">{rf.riskFactorType}</td>
                <td className="py-2 pr-3 text-ink-muted">{rf.riskFactorSubType}</td>
                <td className="py-2 pr-3 text-ink-muted">{rf.tenor || "—"}</td>
                <td className="py-2 pr-3 text-ink-muted">{rf.currency}</td>
                <td className="py-2 pr-3 text-right tabular">{fmtNumber(rf.latest_value, rf.riskFactorType === "Interest Rate" ? 2 : 4)}</td>
                <td className="py-2 pr-3 text-right tabular text-ink-muted">{fmtNumber(rf.historical_min, rf.riskFactorType === "Interest Rate" ? 2 : 4)}</td>
                <td className="py-2 pr-3 text-right tabular text-ink-muted">{fmtNumber(rf.historical_max, rf.riskFactorType === "Interest Rate" ? 2 : 4)}</td>
                <td className={`py-2 pr-3 text-right tabular font-medium ${
                  rf.latest_movement && rf.latest_movement.value < 0 ? "text-negative" : "text-positive"
                }`}>
                  {fmtMovement(rf.latest_movement)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
