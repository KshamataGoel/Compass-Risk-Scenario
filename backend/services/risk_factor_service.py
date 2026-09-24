"""Associated risk factors & their historical observation statistics.

Traces exposure only (position -> instrument -> map -> risk_factor). This proves
ASSOCIATION, never contribution, so risk factors are labelled 'Associated'.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository

# Risk-factor types whose observations are quoted as rates (movement in bps).
RATE_TYPES = {"Interest Rate"}


class RiskFactorService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def associated_risk_factor_ids(self, instrument_ids: list[str]) -> list[str]:
        mapping = self.repo.get("instrument_risk_factor_map")
        subset = mapping[mapping["instrumentId"].isin(instrument_ids)]
        return sorted(subset["riskFactorId"].dropna().unique().tolist())

    def get_associated_risk_factors(self, instrument_ids: list[str], lookback_days: int) -> list[dict[str, Any]]:
        rf_ids = self.associated_risk_factor_ids(instrument_ids)
        risk_factor = self.repo.get("risk_factor")
        obs = self.repo.get("risk_factor_obs")
        mapping = self.repo.get("instrument_risk_factor_map")

        out: list[dict[str, Any]] = []
        for rf_id in rf_ids:
            rf_row = risk_factor[risk_factor["riskFactorId"] == rf_id]
            if rf_row.empty:
                continue
            rf = rf_row.iloc[0]
            series = self._observation_series(obs, rf_id, lookback_days)
            latest_move = self._latest_movement(series, rf["riskFactorType"])
            linked_instruments = sorted(
                mapping.loc[
                    (mapping["riskFactorId"] == rf_id) & (mapping["instrumentId"].isin(instrument_ids)),
                    "instrumentId",
                ].unique().tolist()
            )
            values = [p["value"] for p in series]
            out.append(
                {
                    "riskFactorId": rf_id,
                    "riskFactorName": rf.get("riskFactorName"),
                    "riskFactorType": rf.get("riskFactorType"),
                    "riskFactorSubType": rf.get("riskFactorSubType"),
                    "tenor": None if pd.isna(rf.get("tenor")) else rf.get("tenor"),
                    "currency": rf.get("quoteCurrency"),
                    "unit": series[-1]["unit"] if series else None,
                    "latest_value": values[-1] if values else None,
                    "historical_min": min(values) if values else None,
                    "historical_max": max(values) if values else None,
                    "observation_count": len(values),
                    "latest_movement": latest_move,
                    "linked_instruments": linked_instruments,
                }
            )
        return out

    def _observation_series(self, obs: pd.DataFrame, rf_id: str, lookback_days: int) -> list[dict[str, Any]]:
        sub = obs[obs["riskFactorId"] == rf_id].copy()
        if sub.empty:
            return []
        sub["_date"] = pd.to_datetime(sub["observationDate"], errors="coerce")
        sub = sub.sort_values("_date")
        # Lookback keeps the most recent N trading days of observations.
        if lookback_days and lookback_days > 0:
            sub = sub.tail(lookback_days)
        return [
            {
                "date": str(r["_date"].date()) if pd.notna(r["_date"]) else None,
                "value": float(r["observedValue"]),
                "unit": r.get("observationUnit"),
            }
            for _, r in sub.iterrows()
        ]

    @staticmethod
    def _latest_movement(series: list[dict[str, Any]], rf_type: str) -> dict[str, Any] | None:
        if len(series) < 2:
            return None
        prev, cur = series[-2]["value"], series[-1]["value"]
        if rf_type in RATE_TYPES:
            # Rates are quoted in %, so a difference of 0.04% == 4 bps.
            bps = round((cur - prev) * 100.0, 4)
            return {"basis": "bps", "value": bps, "from": prev, "to": cur, "method": "difference x100 (percent -> bps)"}
        pct = round((cur / prev - 1.0) * 100.0, 6) if prev != 0 else None
        return {"basis": "%", "value": pct, "from": prev, "to": cur, "method": "(current / previous) - 1"}
