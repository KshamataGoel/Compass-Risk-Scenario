"""Historical market movements for the associated risk factors.

Computes the full time series of 1-day movements per risk factor across the
selected lookback (bps for interest rates, % for FX / price-like factors).

IMPORTANT (governance): the workbook contains no instrument pricing / revaluation
model, so an independent full Historical-Simulation revaluation of the current
positions under each historical shock is NOT calculable. That component is
reported as UNAVAILABLE rather than invented. The stored VaR (already computed by
Historical Simulation per risk_metric_mr.methodology) remains the metric of record.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository
from backend.models.response_models import NOT_CALCULABLE
from backend.services.risk_factor_service import RATE_TYPES


class HistoricalSimulationService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def historical_movements(self, risk_factor_ids: list[str], lookback_days: int) -> dict[str, Any]:
        risk_factor = self.repo.get("risk_factor")
        obs = self.repo.get("risk_factor_obs")
        rf_type_map = dict(zip(risk_factor["riskFactorId"], risk_factor["riskFactorType"]))
        rf_name_map = dict(zip(risk_factor["riskFactorId"], risk_factor["riskFactorName"]))

        factors: list[dict[str, Any]] = []
        for rf_id in risk_factor_ids:
            sub = obs[obs["riskFactorId"] == rf_id].copy()
            if sub.empty:
                continue
            sub["_date"] = pd.to_datetime(sub["observationDate"], errors="coerce")
            sub = sub.sort_values("_date")
            if lookback_days and lookback_days > 0:
                sub = sub.tail(lookback_days)

            rf_type = rf_type_map.get(rf_id)
            is_rate = rf_type in RATE_TYPES
            rows = sub.to_dict("records")
            movements = []
            for i in range(1, len(rows)):
                prev_v = float(rows[i - 1]["observedValue"])
                cur_v = float(rows[i]["observedValue"])
                if is_rate:
                    move = round((cur_v - prev_v) * 100.0, 4)
                    basis = "bps"
                else:
                    move = round((cur_v / prev_v - 1.0) * 100.0, 6) if prev_v != 0 else None
                    basis = "%"
                movements.append(
                    {
                        "date": str(rows[i]["_date"].date()) if pd.notna(rows[i]["_date"]) else None,
                        "previous_value": prev_v,
                        "current_value": cur_v,
                        "movement": move,
                        "basis": basis,
                    }
                )

            observed_values = [float(r["observedValue"]) for r in rows]
            move_values = [m["movement"] for m in movements if m["movement"] is not None]
            factors.append(
                {
                    "riskFactorId": rf_id,
                    "riskFactorName": rf_name_map.get(rf_id),
                    "riskFactorType": rf_type,
                    "basis": "bps" if is_rate else "%",
                    "unit": rows[-1].get("observationUnit") if rows else None,
                    "observations": [
                        {
                            "date": str(r["_date"].date()) if pd.notna(r["_date"]) else None,
                            "value": float(r["observedValue"]),
                        }
                        for r in rows
                    ],
                    "movements": movements,
                    "largest_adverse_move": (min(move_values) if move_values else None),
                    "largest_favourable_move": (max(move_values) if move_values else None),
                    "latest_move": movements[-1]["movement"] if movements else None,
                }
            )

        return {
            "lookback_days": lookback_days,
            "method": "1-day movements; interest rates in bps (percent difference x100), other factors in % ((current/previous)-1).",
            "factors": factors,
            "full_revaluation": {
                "status": "UNAVAILABLE",
                "message": NOT_CALCULABLE,
                "reason": (
                    "The workbook provides risk-factor observations and stored VaR results but no instrument "
                    "pricing/revaluation model, so positions cannot be independently repriced under each historical "
                    "shock. Stored Historical-Simulation VaR (risk_metric_mr_obs) is used as the metric of record."
                ),
            },
        }
