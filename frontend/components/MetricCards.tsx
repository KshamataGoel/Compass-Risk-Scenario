"use client";
import React from "react";
import type { Metric } from "@/lib/types";
import { Card, InfoDot, SectionHeader, StatusBadge } from "./ui";
import { fmtMoney, fmtNumber } from "@/lib/format";

// Money metrics: red when negative, neutral ink otherwise (VaR is shown as a positive
// loss magnitude, so it must not read as a green "gain").
function moneyColor(v: number | null | undefined): string {
  return v !== null && v !== undefined && v < 0 ? "text-negative" : "text-ink";
}

// Maps a metric name to a lineage key (a superset key that exists in result.lineage).
const LINEAGE_KEY: Record<string, string> = {
  "Simulation VaR": "Simulation VaR",
  "Previous Simulation VaR": "Previous Simulation VaR",
  "VaR Variance": "VaR Change",
  "VaR Variance %": "VaR Change",
  "VaR Trend": "VaR Change",
  "Warning Threshold": "Warning Threshold",
  "VaR Utilisation": "VaR Utilisation",
  "Portfolio Market Value": "Portfolio",
  "Position Count": "Portfolio",
  "Trade Count": "Portfolio",
  "Instrument Count": "Portfolio",
  "Worst Historical P&L": "Simulation VaR",
  "Best Historical P&L": "Simulation VaR",
  "Average Historical P&L": "Simulation VaR",
  "P&L Observation Count": "Simulation VaR",
  "Risk Factor Count": "Associated Risk Factors",
  "Scenario Count": "Scenario",
};

function display(m: Metric): string {
  if (m.display) return m.display; // e.g. VaR Trend classification ("Decreased")
  if (m.value === null || m.value === undefined) return "—";
  if (m.unit === "%") return `${fmtNumber(m.value, 1)}%`;
  if (m.unit === "count") return fmtNumber(m.value);
  return fmtMoney(m.value, m.unit || "USD");
}

export function MetricCards({
  metrics,
  onLineage,
}: {
  metrics: Metric[];
  onLineage: (key: string) => void;
}) {
  if (!metrics.length) return null;
  return (
    <Card className="p-5">
      <SectionHeader
        title="Market Risk Metrics"
        subtitle="Shown before any commentary. Each figure is tagged STORED, CALCULATED or UNAVAILABLE with its workbook source."
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {metrics.map((m) => {
          const isMoneySigned = m.unit !== "count" && m.unit !== "%";
          return (
            <div key={m.metric_name} className="rounded-lg border border-line p-3.5">
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-medium text-ink-muted">{m.metric_name}</span>
                <StatusBadge status={m.status} />
              </div>
              <div className={`mt-2 text-xl font-semibold tabular ${isMoneySigned ? moneyColor(m.value) : "text-ink"}`}>
                {display(m)}
              </div>
              <div className="mt-2 flex items-center justify-between">
                <code className="truncate text-[10px] text-ink-muted" title={m.source}>
                  {m.source}
                </code>
                {LINEAGE_KEY[m.metric_name] && <InfoDot onClick={() => onLineage(LINEAGE_KEY[m.metric_name])} />}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
