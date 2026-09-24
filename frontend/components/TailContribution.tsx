"use client";
import React, { useState } from "react";
import type { TailContribution as TailContributionType } from "@/lib/types";
import { Card, EmptyNote, Pill, SectionHeader } from "./ui";
import { BarChart } from "./Charts";
import { fmtMoney, fmtNumber } from "@/lib/format";

// Decomposition of the single historical P&L observation the VaR selected.
// NOT Marginal / Component / Incremental VaR — it explains the chosen tail loss.
export function TailContribution({ tail, unit = "USD" }: { tail: TailContributionType; unit?: string }) {
  const [showPositions, setShowPositions] = useState(false);

  if (!tail?.available) {
    return (
      <Card className="p-5">
        <SectionHeader title="VaR Tail Loss Contribution" />
        <EmptyNote>{tail?.message || "No loss tail to decompose (Simulation VaR = 0)."}</EmptyNote>
      </Card>
    );
  }

  const byExposure = tail.by_exposure || [];
  const byAssetClass = tail.by_asset_class || [];

  return (
    <Card className="p-5">
      <SectionHeader
        title="VaR Tail Loss Contribution"
        subtitle={`Decomposition of the selected VaR-tail P&L (${tail.tail_start_date} → ${tail.tail_end_date}). Share of the net tail P&L — not Marginal/Component/Incremental VaR.`}
        right={
          tail.reconciled === false ? <Pill tone="warn">Does not reconcile</Pill> : <Pill tone="accent">Reconciled</Pill>
        }
      />

      {/* Main driver banner */}
      {tail.main_tail_loss_driver && (
        <div className="mb-4 rounded-md border border-negative/30 bg-negative/5 p-3">
          <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-muted">Main tail loss driver</div>
          <div className="mt-0.5 flex flex-wrap items-baseline gap-2">
            <span className="text-lg font-semibold text-ink">{tail.main_tail_loss_driver}</span>
            <span className="tabular text-negative">{fmtMoney(tail.main_tail_loss_amount ?? null, unit)}</span>
            <span className="text-sm text-ink-muted">
              ({tail.main_tail_loss_share_pct}% of the selected VaR-tail net P&L of {fmtMoney(tail.net_tail_pnl ?? null, unit)})
            </span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* By exposure */}
        <div className="rounded-md border border-line p-3">
          <p className="mb-2 text-xs font-semibold text-ink-muted">Tail P&L by Exposure</p>
          <BarChart data={byExposure.map((e) => ({ label: e.exposure, value: e.tail_pnl }))} currency={unit} height={Math.max(120, byExposure.length * 30)} />
          <table className="mt-2 w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="py-1.5 pr-3 font-semibold">Exposure</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Tail P&L</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Share</th>
                <th className="py-1.5 pr-3 font-semibold">Interpretation</th>
              </tr>
            </thead>
            <tbody>
              {byExposure.map((e, i) => (
                <tr key={i} className="border-b border-line/60">
                  <td className="py-1.5 pr-3 font-medium text-ink">{e.exposure}</td>
                  <td className={`py-1.5 pr-3 text-right tabular ${e.tail_pnl < 0 ? "text-negative" : "text-positive"}`}>{fmtMoney(e.tail_pnl, unit)}</td>
                  <td className="py-1.5 pr-3 text-right tabular text-ink-muted">{e.share_pct == null ? "—" : `${e.share_pct}%`}</td>
                  <td className={`py-1.5 pr-3 text-xs ${e.classification === "Loss offset" ? "text-positive" : "text-ink-muted"}`}>{e.classification}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* By asset class */}
        <div className="rounded-md border border-line p-3">
          <p className="mb-2 text-xs font-semibold text-ink-muted">Tail P&L by Asset Class</p>
          <p className="mb-2 text-[11px] text-ink-muted">Distinct from “Market Value by Asset Class” — this is P&L contribution, not exposure market value.</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                <th className="py-1.5 pr-3 font-semibold">Asset Class</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Tail P&L</th>
                <th className="py-1.5 pr-3 text-right font-semibold">Share</th>
              </tr>
            </thead>
            <tbody>
              {byAssetClass.map((a, i) => (
                <tr key={i} className="border-b border-line/60">
                  <td className="py-1.5 pr-3 font-medium text-ink">{a.exposure}</td>
                  <td className={`py-1.5 pr-3 text-right tabular ${a.tail_pnl < 0 ? "text-negative" : "text-positive"}`}>{fmtMoney(a.tail_pnl, unit)}</td>
                  <td className="py-1.5 pr-3 text-right tabular text-ink-muted">{a.share_pct == null ? "—" : `${a.share_pct}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Position detail (collapsible, for validation) */}
      <div className="mt-3">
        <button onClick={() => setShowPositions((v) => !v)} className="text-sm font-medium text-accent hover:underline">
          {showPositions ? "▼ Hide position detail" : "▶ Show position detail (reconciliation)"}
        </button>
        {showPositions && (
          <div className="mt-2 overflow-x-auto scroll-thin">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
                  <th className="py-1.5 pr-3 font-semibold">Position</th>
                  <th className="py-1.5 pr-3 font-semibold">Exposure</th>
                  <th className="py-1.5 pr-3 text-right font-semibold">Start MV</th>
                  <th className="py-1.5 pr-3 text-right font-semibold">End MV</th>
                  <th className="py-1.5 pr-3 text-right font-semibold">Tail P&L</th>
                </tr>
              </thead>
              <tbody>
                {(tail.positions || []).map((p, i) => (
                  <tr key={i} className="border-b border-line/60">
                    <td className="py-1.5 pr-3 font-medium text-ink">{p.positionId}</td>
                    <td className="py-1.5 pr-3 text-ink-muted">{p.exposure}</td>
                    <td className="py-1.5 pr-3 text-right tabular text-ink-muted">{fmtNumber(p.starting_value)}</td>
                    <td className="py-1.5 pr-3 text-right tabular text-ink-muted">{fmtNumber(p.ending_value)}</td>
                    <td className={`py-1.5 pr-3 text-right tabular ${p.tail_pnl < 0 ? "text-negative" : "text-positive"}`}>{p.tail_pnl > 0 ? "+" : ""}{fmtNumber(p.tail_pnl)}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-line font-semibold">
                  <td className="py-1.5 pr-3" colSpan={4}>Net tail P&L (reconciles to VaR tail)</td>
                  <td className={`py-1.5 pr-3 text-right tabular ${(tail.net_tail_pnl ?? 0) < 0 ? "text-negative" : "text-positive"}`}>{fmtNumber(tail.net_tail_pnl ?? 0)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Card>
  );
}
