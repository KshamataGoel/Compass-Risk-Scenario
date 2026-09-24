"""Risk-metric reference helpers.

IMPORTANT: This service NO LONGER produces the Current/Simulation VaR. The stored
risk_metric_mr_obs / risk_metric_obs values (the -$38m RMT001 figure) are not used
as the current simulation result — that is calculated by SimulationVarService.

What remains here is reference-only wiring:
  * aggregate_metric_id -> locate the VaR metric for the portfolio scope, used ONLY
    to find the applicable reference warning threshold (never its metricValue).
  * config_for -> read the stored scenario set for the metric (used by the scenario
    dimension), never to override user request parameters.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository


class RiskMetricService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def _business_unit_names(self) -> dict[str, str]:
        bu = self.repo.get("hsbc_global_Business_Unit")
        return dict(zip(bu["businessUnitId"], bu["hsbcGlobalBusinessFrameworkUnitName"]))

    def aggregate_metric_id(self, portfolio_type: str) -> str | None:
        """The VaR metric representing the whole selected portfolio scope.

        Derived by matching the portfolio type word (e.g. 'Trading') against the
        business-unit name attached to each VaR risk_metric. Used only to locate the
        applicable reference threshold — its stored metricValue is never read.
        """
        rm = self.repo.get("risk_metric")
        bu_names = self._business_unit_names()
        keyword = portfolio_type.split()[0].lower()
        candidates = []
        for _, row in rm.iterrows():
            name = str(bu_names.get(row.get("businessUnitId"), "")).lower()
            if keyword in name:
                candidates.append(row["riskMetricId"])
        if candidates:
            thr = self.repo.get("risk_threshold", required=False)
            if thr is not None and "riskMetricId" in thr.columns:
                thr_ids = set(thr["riskMetricId"])
                for c in candidates:
                    if c in thr_ids:
                        return c
            return candidates[0]
        return None

    def config_for(self, metric_id: str) -> dict[str, Any]:
        """Stored configuration for a metric. Reference only — never overrides the
        user's requested horizon / lookback / confidence."""
        cfg = self.repo.get("risk_metric_mr")
        row = cfg[cfg["riskMetricId"] == metric_id]
        if row.empty:
            return {}
        r = row.iloc[0]
        return {
            "confidenceLevel": _num(r.get("confidenceLevel")),
            "timeHorizonDays": _num(r.get("timeHorizonDays")),
            "calculationWindowDays": _num(r.get("calculationWindowDays")),
            "methodology": r.get("methodology"),
            "scenarioSetId": r.get("scenarioSetId"),
        }


def _num(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)
