"use client";
import React, { useState } from "react";
import { Card, EmptyNote, Pill, SectionHeader } from "./ui";

export function HistoricalMovements({ historical }: { historical: Record<string, any> }) {
  const factors: any[] = historical?.factors || [];
  const [active, setActive] = useState(0);
  if (!factors.length) {
    return (
      <Card className="p-5">
        <SectionHeader title="Historical Market Movements" />
        <EmptyNote>No historical observations available.</EmptyNote>
      </Card>
    );
  }
  const f = factors[active];
  const moves: any[] = f.movements || [];

  return (
    <Card className="p-5">
      <SectionHeader
        title="Historical Market Movements"
        subtitle={historical.method}
        right={
          <Pill tone="warn">Full revaluation: {historical?.full_revaluation?.status || "UNAVAILABLE"}</Pill>
        }
      />
      <div className="mb-3 flex flex-wrap gap-1.5">
        {factors.map((ff, i) => (
          <button
            key={ff.riskFactorId}
            onClick={() => setActive(i)}
            className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
              i === active ? "border-accent bg-accent text-white" : "border-line text-ink-muted hover:bg-slate-50"
            }`}
          >
            {ff.riskFactorName}
          </button>
        ))}
      </div>

      <div className="mb-2 flex flex-wrap gap-4 text-xs text-ink-muted">
        <span>Basis: <span className="font-semibold text-ink">{f.basis}</span></span>
        <span>Largest adverse: <span className="font-semibold text-negative tabular">{fmtMove(f.largest_adverse_move, f.basis)}</span></span>
        <span>Largest favourable: <span className="font-semibold text-positive tabular">{fmtMove(f.largest_favourable_move, f.basis)}</span></span>
      </div>

      <div className="overflow-x-auto scroll-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
              <th className="py-2 pr-4 font-semibold">Date</th>
              <th className="py-2 pr-4 text-right font-semibold">Previous</th>
              <th className="py-2 pr-4 text-right font-semibold">Current</th>
              <th className="py-2 pr-4 text-right font-semibold">1-Day Movement ({f.basis})</th>
            </tr>
          </thead>
          <tbody>
            {moves.map((m, i) => (
              <tr key={i} className="border-b border-line/60">
                <td className="py-1.5 pr-4 text-ink-muted">{m.date}</td>
                <td className="py-1.5 pr-4 text-right tabular">{m.previous_value}</td>
                <td className="py-1.5 pr-4 text-right tabular">{m.current_value}</td>
                <td className={`py-1.5 pr-4 text-right tabular font-medium ${m.movement < 0 ? "text-negative" : "text-positive"}`}>
                  {m.movement > 0 ? "+" : ""}{m.movement}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function fmtMove(v: number | null, basis: string): string {
  if (v === null || v === undefined) return "—";
  return `${v > 0 ? "+" : ""}${v}${basis === "bps" ? " bps" : "%"}`;
}
