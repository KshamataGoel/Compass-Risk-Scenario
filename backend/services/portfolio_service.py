"""Portfolio scope resolution.

Determines the current portfolio from the latest position.asOfDate, filtered by
trade.tradingBookFlag. Aggregations are performed strictly at the position grain
to avoid any double counting.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository
from backend.models.response_models import NOT_AVAILABLE

# Map a user-facing portfolio type to the tradingBookFlag value that defines it.
PORTFOLIO_TYPE_FLAG = {"Trading": "Y", "Non-Trading": "N"}


class PortfolioService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def available_portfolio_types(self) -> list[dict[str, Any]]:
        """Only portfolio types that actually map to workbook records are 'available'."""
        trade = self.repo.get("trade")
        flags = set(trade["tradingBookFlag"].dropna().unique()) if "tradingBookFlag" in trade.columns else set()
        options = []
        for label, flag in PORTFOLIO_TYPE_FLAG.items():
            available = flag in flags
            options.append(
                {
                    "label": label,
                    "value": label,
                    "available": available,
                    "trade_count": int((trade["tradingBookFlag"] == flag).sum()) if "tradingBookFlag" in trade.columns else 0,
                    "reason": None if available else f"No trades with tradingBookFlag = '{flag}' in the workbook.",
                }
            )
        return options

    def get_current_portfolio(self, portfolio_type: str = "Trading") -> dict[str, Any]:
        flag = PORTFOLIO_TYPE_FLAG.get(portfolio_type)
        trade = self.repo.get("trade")
        position = self.repo.get("position")

        if flag is None or "tradingBookFlag" not in trade.columns:
            return {"available": False, "message": NOT_AVAILABLE, "portfolio_type": portfolio_type}

        trading_trade_ids = set(trade.loc[trade["tradingBookFlag"] == flag, "tradeId"])
        if not trading_trade_ids:
            return {
                "available": False,
                "message": "No positions available for selected portfolio type.",
                "portfolio_type": portfolio_type,
            }

        # Latest snapshot across positions belonging to the in-scope trades.
        scoped = position[position["tradeId"].isin(trading_trade_ids)].copy()
        if scoped.empty:
            return {
                "available": False,
                "message": "No positions available for selected portfolio type.",
                "portfolio_type": portfolio_type,
            }

        scoped["_asof"] = pd.to_datetime(scoped["asOfDate"], errors="coerce")
        as_of = scoped["_asof"].max()
        current = scoped[scoped["_asof"] == as_of].drop(columns="_asof")

        # Position-grain aggregation — each position counted exactly once.
        instruments = self.repo.get("instrument")
        book = self.repo.get("book")
        desk = self.repo.get("desk")

        book_names = self._lookup_names(current["bookId"], book, "bookId", "bookName")
        desk_names = self._lookup_names(current["deskId"], desk, "deskId", "deskName")
        instr_names = self._lookup_names(current["instrumentId"], instruments, "instrumentId", "instrumentName")

        positions_records = []
        for _, row in current.iterrows():
            positions_records.append(
                {
                    "positionId": row["positionId"],
                    "tradeId": row["tradeId"],
                    "instrumentId": row["instrumentId"],
                    "bookId": row["bookId"],
                    "deskId": row["deskId"],
                    "quantity": _num(row.get("quantity")),
                    "marketValueBcy": _num(row.get("marketValueBcy")),
                    "positionCurrency": row.get("positionCurrency"),
                }
            )

        return {
            "available": True,
            "portfolio_type": portfolio_type,
            "as_of_date": str(as_of.date()) if pd.notna(as_of) else None,
            "position_count": int(len(current)),
            "trade_count": int(current["tradeId"].nunique()),
            "instrument_count": int(current["instrumentId"].nunique()),
            "book_count": int(current["bookId"].nunique()),
            "desk_count": int(current["deskId"].nunique()),
            "total_market_value_bcy": float(current["marketValueBcy"].sum()),
            "base_currency": _first(current.get("baseCurrency")),
            "books": book_names,
            "desks": desk_names,
            "instruments": instr_names,
            "trade_ids": sorted(current["tradeId"].unique().tolist()),
            "instrument_ids": sorted(current["instrumentId"].unique().tolist()),
            "position_ids": sorted(current["positionId"].unique().tolist()),
            "positions": positions_records,
        }

    @staticmethod
    def _lookup_names(id_series: pd.Series, ref: pd.DataFrame, id_col: str, name_col: str) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        name_map = dict(zip(ref[id_col], ref[name_col])) if name_col in ref.columns else {}
        for _id in id_series:
            if _id in seen:
                continue
            seen.add(_id)
            out.append({"id": _id, "name": name_map.get(_id, _id)})
        return out


def _num(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def _first(series: Any) -> Any:
    if series is None:
        return None
    s = series.dropna()
    return s.iloc[0] if not s.empty else None
