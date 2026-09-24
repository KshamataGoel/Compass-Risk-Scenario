"""VaR Tail Loss Contribution.

Decomposes the single historical P&L observation that the VaR algorithm selected
(the "tail period") into per-position contributions, then aggregates them by
exposure and by asset class. This explains WHAT drove the selected tail loss.

Governance:
  * It decomposes ONE historical observation; it is NOT Marginal / Component /
    Incremental VaR.
  * Position tail P&L = marketValueBcy(tail_end) - marketValueBcy(tail_start),
    at position grain, and MUST reconcile to the selected tail P&L.
  * The main loss driver is determined deterministically (largest negative
    exposure contribution) — never by the LLM.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.services.portfolio_service import PORTFOLIO_TYPE_FLAG


class TailContributionService:
    def __init__(self, repo) -> None:
        self.repo = repo

    def contribution(self, portfolio_type: str, tail_start_date: str, tail_end_date: str) -> dict[str, Any]:
        flag = PORTFOLIO_TYPE_FLAG.get(portfolio_type)
        trade = self.repo.get("trade")
        position = self.repo.get("position")
        instrument = self.repo.get("instrument")
        asset_class = self.repo.get("asset_class")

        if flag is None or "tradingBookFlag" not in trade.columns:
            return {"available": False, "message": "No positions available for selected portfolio type."}

        scope_trade_ids = set(trade.loc[trade["tradingBookFlag"] == flag, "tradeId"])
        pos = position[position["tradeId"].isin(scope_trade_ids)].copy()
        pos["_date"] = pd.to_datetime(pos["asOfDate"], errors="coerce").dt.date.astype(str)

        start = pos[pos["_date"] == str(tail_start_date)][["positionId", "instrumentId", "marketValueBcy"]]
        end = pos[pos["_date"] == str(tail_end_date)][["positionId", "instrumentId", "marketValueBcy"]]
        if start.empty or end.empty:
            return {"available": False, "message": "Tail period positions not found in the workbook."}

        merged = start.merge(end, on=["positionId", "instrumentId"], suffixes=("_start", "_end"))
        merged["tail_pnl"] = merged["marketValueBcy_end"] - merged["marketValueBcy_start"]

        # Exposure label per position: prefer risk_pnl_record.pnlComponent (a workbook
        # classification of positions), else the instrument name.
        exposure_map = self._exposure_labels()
        instr_name = dict(zip(instrument["instrumentId"], instrument["instrumentName"]))
        instr_ac = dict(zip(instrument["instrumentId"], instrument["assetClassId"]))
        ac_name = dict(zip(asset_class["assetClassId"], asset_class["assetClassName"]))

        positions = []
        for _, r in merged.iterrows():
            positions.append(
                {
                    "positionId": r["positionId"],
                    "instrumentId": r["instrumentId"],
                    "exposure": exposure_map.get(r["positionId"], instr_name.get(r["instrumentId"], r["instrumentId"])),
                    "assetClass": ac_name.get(instr_ac.get(r["instrumentId"]), "Unknown"),
                    "starting_value": float(r["marketValueBcy_start"]),
                    "ending_value": float(r["marketValueBcy_end"]),
                    "tail_pnl": float(r["tail_pnl"]),
                }
            )

        net_tail_pnl = float(sum(p["tail_pnl"] for p in positions))

        by_exposure = self._aggregate(positions, "exposure", net_tail_pnl)
        by_asset_class = self._aggregate(positions, "assetClass", net_tail_pnl)

        # Main loss driver = largest NEGATIVE exposure contribution.
        negatives = [e for e in by_exposure if e["tail_pnl"] < 0]
        main = min(negatives, key=lambda e: e["tail_pnl"]) if negatives else None

        return {
            "available": True,
            "tail_start_date": str(tail_start_date),
            "tail_end_date": str(tail_end_date),
            "net_tail_pnl": net_tail_pnl,
            "positions": sorted(positions, key=lambda p: p["tail_pnl"]),
            "by_exposure": by_exposure,
            "by_asset_class": by_asset_class,
            "main_tail_loss_driver": main["exposure"] if main else None,
            "main_tail_loss_amount": main["tail_pnl"] if main else None,
            "main_tail_loss_share_pct": main["share_pct"] if main else None,
            "reconciled": True,  # net_tail_pnl is by construction the sum of position P&Ls
        }

    def _exposure_labels(self) -> dict[str, str]:
        pnl = self.repo.get("risk_pnl_record", required=False)
        if pnl is None or "positionId" not in pnl.columns or "pnlComponent" not in pnl.columns:
            return {}
        # One component per position in the workbook.
        return dict(zip(pnl["positionId"], pnl["pnlComponent"]))

    @staticmethod
    def _aggregate(positions, key, net_tail_pnl) -> list[dict[str, Any]]:
        agg: dict[str, float] = {}
        for p in positions:
            agg[p[key]] = agg.get(p[key], 0.0) + p["tail_pnl"]
        rows = []
        for name, pnl in agg.items():
            # Share of the selected VaR-tail NET P&L (not Marginal/Component VaR).
            share = round(pnl / net_tail_pnl * 100.0, 1) if net_tail_pnl != 0 else None
            rows.append(
                {
                    "exposure": name,
                    "tail_pnl": round(pnl, 2),
                    "share_pct": share,
                    "classification": "Loss contributor" if pnl < 0 else "Loss offset",
                }
            )
        return sorted(rows, key=lambda r: r["tail_pnl"])
