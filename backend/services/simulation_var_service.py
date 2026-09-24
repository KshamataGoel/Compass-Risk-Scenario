"""Real-time Historical Simulation VaR.

Calculates VaR at request time from the portfolio's own market-value history. It has
NO dependency on the stored risk_metric_mr_obs / risk_metric_obs (-$38m) values.

Semantics (per the corrections):
  * Historical (P&L) Lookback = N means N historical P&L OBSERVATIONS, not N dates.
    For a horizon of H trading days, N observations require (N + H) ordered valuation
    dates.
  * VaR = max(0, -lower_tail_pnl), where
        lower_tail_pnl = quantile(pnl, 1 - confidence, method="lower").
    A negative lower tail becomes a positive VaR loss; a positive lower tail => VaR 0.
  * A point-in-time VaR "as of" date D uses only valuation dates <= D.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from backend.data.excel_repository import ExcelRepository
from backend.services.portfolio_service import PORTFOLIO_TYPE_FLAG

logger = logging.getLogger("simulation")

INSUFFICIENT = "Insufficient historical data."
TREND_THRESHOLD_PCT = 5.0   # |variance %| within this band => "Steady"
TREND_POINTS = 6            # number of latest valid as-of dates plotted in the trend


class SimulationVarService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    # ----------------------------------------------- portfolio value history
    def portfolio_value_history(self, portfolio_type: str) -> dict[str, Any]:
        """PortfolioValue(date) = SUM(position.marketValueBcy) for in-scope trades."""
        flag = PORTFOLIO_TYPE_FLAG.get(portfolio_type)
        trade = self.repo.get("trade")
        position = self.repo.get("position")
        if flag is None or "tradingBookFlag" not in trade.columns:
            return {"available": False, "message": "No positions available for selected portfolio type."}

        scope_trade_ids = set(trade.loc[trade["tradingBookFlag"] == flag, "tradeId"])
        if not scope_trade_ids:
            return {"available": False, "message": "No positions available for selected portfolio type."}

        pos = position[position["tradeId"].isin(scope_trade_ids)].copy()
        if pos.empty:
            return {"available": False, "message": "No positions available for selected portfolio type."}

        pos["_date"] = pd.to_datetime(pos["asOfDate"], errors="coerce")
        grouped = pos.groupby("_date")["marketValueBcy"].sum().sort_index()
        history = [{"date": str(d.date()), "portfolio_value": float(v)} for d, v in grouped.items()]
        return {"available": True, "history": history, "trade_ids": sorted(scope_trade_ids)}

    # ---------------------------------------------------------- calculation
    def calculate(
        self,
        portfolio_type: str,
        lookback_days: int,       # N = number of historical P&L observations
        horizon_days: int,        # H = trading-day horizon
        confidence_level: float,
    ) -> dict[str, Any]:
        hist = self.portfolio_value_history(portfolio_type)
        if not hist.get("available"):
            return {"available": False, "message": hist.get("message")}

        full_history = hist["history"]     # ascending by date
        total_dates = len(full_history)
        horizon = int(horizon_days)
        # lookback_days <= 0 is the "Full history" sentinel: use every available P&L
        # observation for this horizon (N = total valuation dates - horizon).
        n_obs = int(lookback_days)
        if n_obs <= 0:
            n_obs = max(0, total_dates - horizon)

        logger.info("=" * 60)
        logger.info("Simulation Parameters:")
        logger.info("  Portfolio: %s", portfolio_type)
        logger.info("  Horizon: %s", horizon)
        logger.info("  Historical P&L Lookback (observations): %s", n_obs)
        logger.info("  Confidence: %s", confidence_level)
        logger.info("Portfolio History (all %d dates):", total_dates)
        for row in full_history:
            logger.info("  %s -> %s", row["date"], f"{row['portfolio_value']:,.2f}")

        # N observations at horizon H require (N + H) ordered valuation dates.
        if n_obs + horizon > total_dates:
            logger.info("Result: %s (need %d dates, have %d)", INSUFFICIENT, n_obs + horizon, total_dates)
            return {
                "available": False,
                "message": INSUFFICIENT,
                "required_dates": n_obs + horizon,
                "available_dates": total_dates,
                "portfolio_history_full": full_history,
            }

        current = self._compute_var_at(full_history, total_dates - 1, n_obs, horizon, confidence_level, "CURRENT")
        previous = self._compute_var_at(full_history, total_dates - 2, n_obs, horizon, confidence_level, "PREVIOUS")

        var_variance = None
        var_variance_pct = None
        trend_class = None
        if current.get("available") and previous.get("available"):
            var_variance = current["simulation_var"] - previous["simulation_var"]
            var_variance_pct = _variance_pct(current["simulation_var"], previous["simulation_var"])
            trend_class = _classify(var_variance_pct, var_variance)

        # ---- 6-day point-in-time VaR trend (latest TREND_POINTS valid as-of dates).
        trend = self._build_trend(full_history, n_obs, horizon, confidence_level, total_dates)

        logger.info("Simulation VaR: %s", current.get("simulation_var"))
        logger.info("Previous Simulation VaR: %s", previous.get("simulation_var") if previous.get("available") else "UNAVAILABLE")
        logger.info("VaR Variance: %s  (%.2f%%)  -> %s", var_variance, (var_variance_pct if var_variance_pct is not None else float("nan")), trend_class)
        logger.info("Tail period: %s", current.get("tail_period"))
        logger.info("=" * 60)

        return {
            "available": True,
            "portfolio_type": portfolio_type,
            "lookback_days": n_obs,
            "horizon_days": horizon,
            "confidence_level": confidence_level,
            "tail_probability": round(1 - confidence_level / 100.0, 6),
            "methodology": "Historical Simulation (portfolio revaluation from position market-value history)",
            "portfolio_history_full": full_history,
            "portfolio_history_window": current["window"],
            "pnl_distribution": current["pnl_distribution"],
            "pnl_sorted": current["pnl_sorted"],
            "simulation_var": current["simulation_var"],
            "var_as_of_date": current["as_of_date"],
            "tail_quantile": current["tail_quantile"],
            "tail_period": current["tail_period"],
            "worst_pnl": current["worst_pnl"],
            "best_pnl": current["best_pnl"],
            "average_pnl": current["average_pnl"],
            "observation_count": current["observation_count"],
            "previous": previous,
            "previous_simulation_var": previous.get("simulation_var") if previous.get("available") else None,
            "previous_available": previous.get("available", False),
            "previous_as_of_date": previous.get("as_of_date") if previous.get("available") else None,
            "var_change": var_variance,
            "var_variance": var_variance,
            "var_variance_pct": var_variance_pct,
            "var_trend_classification": trend_class,
            "var_trend": trend,
            "trend_threshold_pct": TREND_THRESHOLD_PCT,
            "unit": _base_ccy(self.repo),
        }

    # ------------------------------------------------------------- internals
    def _compute_var_at(self, full_history, end_index, n_obs, horizon, confidence, label) -> dict[str, Any]:
        """Point-in-time VaR using only dates <= full_history[end_index]."""
        need = n_obs + horizon
        start_index = end_index - need + 1
        if end_index < 0 or start_index < 0:
            return {"available": False, "message": INSUFFICIENT}

        window = full_history[start_index : end_index + 1]  # exactly (N + H) dates
        values = [w["portfolio_value"] for w in window]
        dates = [w["date"] for w in window]

        pnl_rows = []
        for i in range(horizon, len(window)):
            start_v = values[i - horizon]
            end_v = values[i]
            pnl_rows.append(
                {
                    "start_date": dates[i - horizon],
                    "end_date": dates[i],
                    "starting_portfolio_value": start_v,
                    "ending_portfolio_value": end_v,
                    "historical_pnl": end_v - start_v,
                }
            )

        pnl_array = np.array([r["historical_pnl"] for r in pnl_rows], dtype=float)
        conf_decimal = confidence_level_to_decimal(confidence)
        tail_prob = 1 - conf_decimal
        lower_tail_pnl = float(np.quantile(pnl_array, tail_prob, method="lower"))
        # Correct VaR: a loss (negative tail) -> positive VaR; a gain -> VaR 0.
        simulation_var = max(0.0, -lower_tail_pnl)

        # The tail period is the P&L observation selected by the quantile, but only
        # when it is an actual loss (VaR > 0).
        tail_period = None
        if simulation_var > 0:
            for r in pnl_rows:
                if r["historical_pnl"] == lower_tail_pnl:
                    tail_period = {
                        "start_date": r["start_date"],
                        "end_date": r["end_date"],
                        "tail_pnl": r["historical_pnl"],
                    }
                    break

        logger.info("[%s] as-of %s window dates: %s", label, dates[-1], dates)
        logger.info("[%s] historical P&L: %s", label, [round(v, 2) for v in pnl_array.tolist()])
        logger.info("[%s] sorted P&L: %s", label, [round(v, 2) for v in np.sort(pnl_array).tolist()])
        logger.info("[%s] tail prob %.4f -> lower_tail %s -> VaR %s", label, tail_prob, lower_tail_pnl, simulation_var)

        return {
            "available": True,
            "as_of_date": dates[-1],
            "window": window,
            "pnl_distribution": pnl_rows,
            "pnl_sorted": sorted(r["historical_pnl"] for r in pnl_rows),
            "tail_quantile": lower_tail_pnl,
            "tail_period": tail_period,
            "simulation_var": simulation_var,
            "worst_pnl": float(pnl_array.min()),
            "best_pnl": float(pnl_array.max()),
            "average_pnl": float(pnl_array.mean()),
            "observation_count": len(pnl_rows),
        }

    def _build_trend(self, full_history, n_obs, horizon, confidence, total_dates) -> list[dict[str, Any]]:
        need = n_obs + horizon
        first_valid_end = need - 1               # earliest end_index with enough history
        last_end = total_dates - 1
        valid_ends = [e for e in range(first_valid_end, last_end + 1)]
        selected = valid_ends[-TREND_POINTS:]    # latest up to TREND_POINTS as-of dates

        points = []
        for e in selected:
            v = self._compute_var_at(full_history, e, n_obs, horizon, confidence, "TREND")
            if v.get("available"):
                points.append({"as_of_date": v["as_of_date"], "simulation_var": v["simulation_var"]})

        # Variance / classification against the previous point in the ascending series.
        out = []
        prev_var = None
        for p in points:
            variance = None
            variance_pct = None
            trend = None
            if prev_var is not None:
                variance = p["simulation_var"] - prev_var
                variance_pct = _variance_pct(p["simulation_var"], prev_var)
                trend = _classify(variance_pct, variance)
            out.append(
                {
                    "as_of_date": p["as_of_date"],
                    "simulation_var": p["simulation_var"],
                    "var_variance": variance,
                    "var_variance_pct": variance_pct,
                    "trend": trend,
                }
            )
            prev_var = p["simulation_var"]
        return out


def confidence_level_to_decimal(confidence: float) -> float:
    return confidence / 100.0 if confidence > 1 else confidence


def _variance_pct(current: float, previous: float) -> float | None:
    if previous == 0:
        return None  # avoid divide-by-zero; UI shows N/A
    return round((current - previous) / previous * 100.0, 2)


def _classify(variance_pct: float | None, variance_amount: float | None) -> str:
    if variance_pct is None:
        # Previous VaR was 0; classify by direction of the absolute change.
        if variance_amount is None or variance_amount == 0:
            return "Steady"
        return "Increased" if variance_amount > 0 else "Decreased"
    if variance_pct > TREND_THRESHOLD_PCT:
        return "Increased"
    if variance_pct < -TREND_THRESHOLD_PCT:
        return "Decreased"
    return "Steady"


def _base_ccy(repo: ExcelRepository) -> str:
    pos = repo.get("position", required=False)
    if pos is not None and "baseCurrency" in pos.columns:
        s = pos["baseCurrency"].dropna()
        if not s.empty:
            return str(s.iloc[0])
    return "USD"
