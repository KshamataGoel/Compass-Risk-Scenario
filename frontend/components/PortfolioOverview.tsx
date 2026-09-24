"use client";
import React from "react";
import { Card, EmptyNote, InfoDot, SectionHeader } from "./ui";
import { fmtMoney, fmtNumber } from "@/lib/format";

export function PortfolioOverview({
  portfolio,
  onLineage,
}: {
  portfolio: Record<string, any>;
  onLineage: () => void;
}) {
  if (!portfolio?.available) {
    return (
      <Card className="p-5">
        <SectionHeader title="Portfolio Overview" />
        <EmptyNote>{portfolio?.message || "No positions available for selected portfolio type."}</EmptyNote>
      </Card>
    );
  }

  const stats = [
    { label: "Positions", value: fmtNumber(portfolio.position_count) },
    { label: "Trades", value: fmtNumber(portfolio.trade_count) },
    { label: "Instruments", value: fmtNumber(portfolio.instrument_count) },
    { label: "Books", value: fmtNumber(portfolio.book_count) },
    { label: "Desks", value: fmtNumber(portfolio.desk_count) },
    { label: "Market Value (BCY)", value: fmtMoney(portfolio.total_market_value_bcy, portfolio.base_currency) },
  ];

  return (
    <Card className="p-5">
      <SectionHeader
        title="Portfolio Overview"
        subtitle={`As of ${portfolio.as_of_date} · ${portfolio.portfolio_type} book`}
        right={<span className="text-xs text-ink-muted">Lineage <InfoDot onClick={onLineage} /></span>}
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {stats.map((s) => (
          <div key={s.label} className="rounded-md border border-line bg-slate-50 px-3 py-3">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-muted">{s.label}</div>
            <div className="mt-1 text-lg font-semibold text-ink tabular">{s.value}</div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap gap-4 text-xs text-ink-muted">
        <span><span className="font-semibold text-ink">Books:</span> {portfolio.books?.map((b: any) => b.name).join(", ")}</span>
        <span><span className="font-semibold text-ink">Desks:</span> {portfolio.desks?.map((d: any) => d.name).join(", ")}</span>
      </div>
    </Card>
  );
}
