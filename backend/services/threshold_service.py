"""Warning threshold & VaR utilisation.

Utilisation = ABS(Current VaR) / applicable warning threshold, where the threshold
is the one bound to the aggregate VaR metric via risk_threshold.riskMetricId.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository
from backend.models.response_models import Metric, MetricStatus


class ThresholdService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def threshold_for(self, metric_id: str) -> dict[str, Any] | None:
        thr = self.repo.get("risk_threshold", required=False)
        if thr is None or "riskMetricId" not in thr.columns:
            return None
        row = thr[thr["riskMetricId"] == metric_id]
        if row.empty:
            return None
        r = row.iloc[0]
        return {
            "thresholdId": r.get("thresholdId"),
            "warning_threshold": float(r.get("thresholdValueHigh")),
            "threshold_low": float(r.get("thresholdValueLow")) if pd.notna(r.get("thresholdValueLow")) else None,
            "riskMetricType": r.get("riskMetricType"),
        }

    def utilisation(self, metric_id: str, current_var: float | None) -> dict[str, Any]:
        thr = self.threshold_for(metric_id)
        if thr is None or current_var is None:
            return {"available": False, "message": "Not available from current data model"}
        warning = thr["warning_threshold"]
        util = abs(current_var) / warning if warning else None
        return {
            "available": True,
            "current_var": current_var,
            "warning_threshold": warning,
            "utilisation": util,
            "utilisation_pct": round(util * 100.0, 2) if util is not None else None,
            "thresholdId": thr["thresholdId"],
        }

    def breaches(self) -> list[dict[str, Any]]:
        b = self.repo.get("risk_threshold_breach", required=False)
        if b is None:
            return []
        return b.where(pd.notna(b), None).to_dict("records")

    def build_metric_cards(self, metric_id: str, current_var: float | None, unit: str = "USD") -> list[Metric]:
        cards: list[Metric] = []
        util = self.utilisation(metric_id, current_var)
        if util.get("available"):
            cards.append(Metric(metric_name="Warning Threshold", value=util["warning_threshold"], unit=unit,
                                status=MetricStatus.STORED, source="risk_threshold.thresholdValueHigh"))
            cards.append(Metric(metric_name="VaR Utilisation", value=util["utilisation_pct"], unit="%",
                                status=MetricStatus.CALCULATED, source="ABS(Current VaR) / Warning Threshold"))
        return cards
