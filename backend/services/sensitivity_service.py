"""Sensitivity dimension.

Reports stored sensitivity values with their currency, associated risk metric and
risk model. Sensitivity is NOT interpreted as VaR contribution.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository


class SensitivityService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def sensitivities(self, metric_ids: list[str] | None = None) -> list[dict[str, Any]]:
        sens = self.repo.get("sensitivity", required=False)
        if sens is None or sens.empty:
            return []
        model = self.repo.get("model", required=False)
        model_type = dict(zip(model["riskModelId"], model["modelType"])) if model is not None and "modelType" in model.columns else {}

        df = sens.copy()
        if metric_ids:
            df = df[df["riskMetricId"].isin(metric_ids)]

        out = []
        for _, r in df.iterrows():
            out.append(
                {
                    "sensitivityId": r.get("sensitivityId"),
                    "riskMetricId": r.get("riskMetricId"),
                    "riskModelId": r.get("riskModelId"),
                    "riskModelType": model_type.get(r.get("riskModelId")),
                    "sensitivityValue": _num(r.get("sensitivityValue")),
                    "currency": r.get("sensitivityValueCurrency"),
                    "asOfDate": str(r.get("asOfDate")),
                    "resultStatus": r.get("resultStatus"),
                }
            )
        return out


def _num(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)
