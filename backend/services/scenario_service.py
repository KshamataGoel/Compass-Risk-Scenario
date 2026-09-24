"""Stress scenario dimension.

Traces scenario_mr -> risk_factor_shock -> risk_factor for shock detail, and
risk_pnl_record for scenario P&L. Stress P&L is aggregated at the positionId grain
to avoid duplication and is never labelled 'VaR'. Scenario sets without any P&L
record are reported as 'Not available from current data model'.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository
from backend.models.response_models import Metric, MetricStatus, NOT_AVAILABLE


class ScenarioService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def scenarios(self, scenario_set_ids: list[str] | None = None, position_ids: list[str] | None = None) -> dict[str, Any]:
        scen = self.repo.get("scenario_mr")
        shocks = self.repo.get("risk_factor_shock")
        rf = self.repo.get("risk_factor")
        pnl = self.repo.get("risk_pnl_record", required=False)
        rf_name = dict(zip(rf["riskFactorId"], rf["riskFactorName"]))

        if scenario_set_ids:
            scen = scen[scen["scenarioSetId"].isin(scenario_set_ids)]

        results = []
        for _, s in scen.iterrows():
            sid = s["scenarioSetId"]
            s_shocks = shocks[shocks["scenarioSetId"] == sid]
            shock_rows = [
                {
                    "riskFactorId": sh["riskFactorId"],
                    "riskFactorName": rf_name.get(sh["riskFactorId"]),
                    "shockType": sh.get("shockType"),
                    "shockValue": _num(sh.get("shockValue")),
                    "shockUnit": sh.get("shockUnit"),
                }
                for _, sh in s_shocks.iterrows()
            ]

            # Scenario P&L (position grain), optionally scoped to current positions.
            scenario_pnl: dict[str, Any]
            if pnl is not None and "scenarioSetId" in pnl.columns:
                p = pnl[pnl["scenarioSetId"] == sid].copy()
                if position_ids is not None:
                    p = p[p["positionId"].isin(position_ids)]
                if p.empty:
                    scenario_pnl = {"available": False, "message": NOT_AVAILABLE}
                else:
                    p = p.drop_duplicates(subset=["positionId"])  # position grain, no double count
                    scenario_pnl = {
                        "available": True,
                        "total_pnl": float(p["amountBaseCcy"].sum()),
                        "record_count": int(len(p)),
                        "by_component": _group_sum(p, "pnlComponent", "amountBaseCcy"),
                        "by_book": _group_sum(p, "bookId", "amountBaseCcy"),
                    }
            else:
                scenario_pnl = {"available": False, "message": NOT_AVAILABLE}

            results.append(
                {
                    "scenarioSetId": sid,
                    "scenarioSetName": s.get("scenarioSetName"),
                    "scenarioType": s.get("scenarioType"),
                    "scenarioDate": str(s.get("scenarioDate")),
                    "shocks": shock_rows,
                    "scenario_pnl": scenario_pnl,
                }
            )
        return {"scenarios": results}

    def stress_pnl_summary(self, scenario_set_id: str | None = None, position_ids: list[str] | None = None) -> dict[str, Any]:
        pnl = self.repo.get("risk_pnl_record", required=False)
        if pnl is None or pnl.empty:
            return {"available": False, "message": NOT_AVAILABLE}
        p = pnl.copy()
        if scenario_set_id:
            p = p[p["scenarioSetId"] == scenario_set_id]
        if position_ids is not None:
            p = p[p["positionId"].isin(position_ids)]
        if p.empty:
            return {"available": False, "message": NOT_AVAILABLE}
        p = p.drop_duplicates(subset=["positionId"])
        return {
            "available": True,
            "scenario_set_id": scenario_set_id,
            "pnl_type": _first(p.get("pnlType")),
            "total_pnl": float(p["amountBaseCcy"].sum()),
            "currency": _first(p.get("baseCurrency")),
            "record_count": int(len(p)),
            "by_component": _group_sum(p, "pnlComponent", "amountBaseCcy"),
            "by_book": _group_sum(p, "bookId", "amountBaseCcy"),
            "by_position": _group_sum(p, "positionId", "amountBaseCcy"),
        }

    def build_metric_cards(self, stress: dict[str, Any]) -> list[Metric]:
        if not stress.get("available"):
            return []
        return [
            Metric(metric_name="Stress Scenario P&L", value=stress["total_pnl"], unit=stress.get("currency") or "USD",
                   status=MetricStatus.STORED, source="SUM(risk_pnl_record.amountBaseCcy) at position grain")
        ]


def _group_sum(df: pd.DataFrame, key: str, val: str) -> list[dict[str, Any]]:
    if key not in df.columns:
        return []
    g = df.groupby(key)[val].sum().reset_index()
    return [{"key": r[key], "value": float(r[val])} for _, r in g.iterrows()]


def _num(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)


def _first(series: Any) -> Any:
    if series is None:
        return None
    s = series.dropna()
    return s.iloc[0] if not s.empty else None
