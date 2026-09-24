"use client";
import React from "react";
import { Card, EmptyNote, InfoDot, SectionHeader } from "./ui";
import { fmtNumber } from "@/lib/format";

export function SensitivityTable({
  sensitivity,
  onLineage,
}: {
  sensitivity: any[];
  onLineage: () => void;
}) {
  return (
    <Card className="p-5">
      <SectionHeader
        title="Sensitivity"
        subtitle="Stored sensitivities (sensitivity). Not interpreted as VaR contribution."
        right={<span className="text-xs text-ink-muted">Lineage <InfoDot onClick={onLineage} /></span>}
      />
      {!sensitivity?.length ? (
        <EmptyNote>No sensitivity data available.</EmptyNote>
      ) : (
        <div className="overflow-x-auto scroll-thin">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="py-2 pr-4 font-semibold">Sensitivity Id</th>
                <th className="py-2 pr-4 font-semibold">Risk Metric</th>
                <th className="py-2 pr-4 font-semibold">Risk Model</th>
                <th className="py-2 pr-4 text-right font-semibold">Value</th>
                <th className="py-2 pr-4 font-semibold">Currency</th>
              </tr>
            </thead>
            <tbody>
              {sensitivity.map((s) => (
                <tr key={s.sensitivityId} className="border-b border-line/60">
                  <td className="py-2 pr-4 font-medium text-ink">{s.sensitivityId}</td>
                  <td className="py-2 pr-4 text-ink-muted">{s.riskMetricId}</td>
                  <td className="py-2 pr-4 text-ink-muted">{s.riskModelId} · {s.riskModelType}</td>
                  <td className={`py-2 pr-4 text-right tabular font-medium ${s.sensitivityValue < 0 ? "text-negative" : "text-positive"}`}>
                    {fmtNumber(s.sensitivityValue)}
                  </td>
                  <td className="py-2 pr-4 text-ink-muted">{s.currency}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
