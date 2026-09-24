"""Config options for the simulation input panel.

Every selectable value is derived from the workbook. Unsupported options are
returned with available=false and a reason, never hidden behind a fabricated value.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository
from backend.services.dimension_service import DimensionService
from backend.services.portfolio_service import PortfolioService


class ConfigService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo
        self.portfolio = PortfolioService(repo)
        self.dimension = DimensionService(repo)

    def options(self) -> dict[str, Any]:
        return {
            "risk_horizons": self._risk_horizons(),
            "portfolio_types": self.portfolio.available_portfolio_types(),
            "lookback_periods": self._lookback_periods(),
            "confidence_levels": self._confidence_levels(),
            "commentary_dimensions": self._dimensions(),
            "model_config_summary": self._model_config(),
        }

    def _trading_days(self) -> int:
        # Horizon/lookback availability is bounded by the number of position snapshot dates.
        pos = self.repo.get("position", required=False)
        if pos is not None and "asOfDate" in pos.columns:
            return int(pd.to_datetime(pos["asOfDate"], errors="coerce").dt.date.nunique())
        return 0

    def _risk_horizons(self) -> list[dict[str, Any]]:
        # Horizon is now computed in Python from position history, so any horizon H is
        # available provided the workbook has more than H trading dates (H+1 needed to
        # form at least one P&L observation).
        total = self._trading_days()
        candidates = [1, 2, 5, 10]
        out = []
        for d in candidates:
            available = d < total
            out.append(
                {
                    "label": f"{d} Day" if d == 1 else f"{d} Days",
                    "value": d,
                    "available": available,
                    "reason": None if available else f"Requires more than {d} trading snapshots; only {total} available.",
                }
            )
        return out

    def _confidence_levels(self) -> list[dict[str, Any]]:
        # Confidence is a genuine user input (not read from risk_metric_mr).
        return [
            {"label": "90%", "value": 90, "available": True},
            {"label": "95%", "value": 95, "available": True},
            {"label": "97.5%", "value": 97.5, "available": True},
            {"label": "98%", "value": 98, "available": True},
            {"label": "99%", "value": 99, "available": True},
        ]

    def _lookback_periods(self) -> list[dict[str, Any]]:
        # Historical (P&L) Lookback = number of historical P&L OBSERVATIONS.
        # For a 1-day horizon, N observations need N+1 valuation dates, so the maximum
        # possible N is (trading dates - 1). Larger horizons reduce this further and are
        # validated per-request by the VaR engine.
        pos = self.repo.get("position", required=False)
        trading_days = 0
        weeks = 0
        if pos is not None and "asOfDate" in pos.columns:
            dates = pd.to_datetime(pos["asOfDate"], errors="coerce").dropna()
            trading_days = int(dates.dt.date.nunique())
            if not dates.empty:
                span_days = (dates.max() - dates.min()).days
                weeks = max(1, round(span_days / 7)) if span_days else 1
        max_obs = max(0, trading_days - 1)
        candidates = [n for n in (2, 3, 5, 9) if 2 <= n <= max_obs]
        if max_obs >= 2 and max_obs not in candidates:
            candidates.append(max_obs)
        out = []
        for n in sorted(set(candidates)):
            out.append({"label": f"{n} Observations", "value": n, "available": True,
                        "hint": "Number of historical P&L observations used in the VaR distribution."})
        # Full-history option (the entire ~N-week dataset). value 0 = "use every available
        # observation for the chosen horizon" (adapts to horizon; 9 obs for a 1-day horizon).
        if max_obs >= 2:
            week_label = f"~{weeks} week{'s' if weeks != 1 else ''}" if weeks else "all data"
            out.append({"label": f"Full history ({week_label})", "value": 0, "available": True,
                        "hint": f"Uses every available P&L observation for the selected horizon (the full {week_label} dataset)."})
        if not out:
            out.append({"label": "Not available from current data model", "value": 0, "available": False})
        return out

    def _dimensions(self) -> list[dict[str, Any]]:
        dims = self.dimension.available_dimensions()
        # Default: select all available dimensions.
        for d in dims:
            d["default_selected"] = bool(d["available"])
        return dims

    def _model_config(self) -> dict[str, Any]:
        cfg = self.repo.get("risk_metric_mr", required=False)
        if cfg is None or cfg.empty:
            return {}
        r = cfg.iloc[0]
        return {
            "confidenceLevel": _num(r.get("confidenceLevel")),
            "timeHorizonDays": _num(r.get("timeHorizonDays")),
            "calculationWindowDays": _num(r.get("calculationWindowDays")),
            "methodology": r.get("methodology"),
            "distributionAssumption": r.get("distributionAssumption"),
            "regulatoryFramework": r.get("regulatoryFramework"),
        }


def _num(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)
