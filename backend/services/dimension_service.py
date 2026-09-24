"""Dimension-level analysis.

Only dimensions that are genuinely derivable from the workbook are offered. Every
market-value aggregation is performed at the position grain (each position counted
once); mapping tables are used only for classification, never for MV aggregation.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository

# Canonical dimensions and the workbook path that makes each derivable.
DIMENSION_DEFS = [
    {"key": "Asset Class", "path": "position -> instrument -> asset_class", "requires": ["position", "instrument", "asset_class"]},
    {"key": "Business", "path": "risk_metric -> businessUnitId -> hsbc_global_Business_Unit", "requires": ["risk_metric", "hsbc_global_Business_Unit"]},
    {"key": "Scenario", "path": "risk_metric_mr.scenarioSetId -> scenario_mr -> risk_factor_shock", "requires": ["scenario_mr", "risk_factor_shock"]},
    {"key": "Risk Factor", "path": "position -> instrument -> instrument_risk_factor_map -> risk_factor", "requires": ["instrument_risk_factor_map", "risk_factor", "risk_factor_obs"]},
    {"key": "Desk", "path": "position.deskId -> desk", "requires": ["position", "desk"]},
    {"key": "Book", "path": "position.bookId -> book", "requires": ["position", "book"]},
    {"key": "Instrument", "path": "position.instrumentId -> instrument", "requires": ["position", "instrument"]},
]


class DimensionService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def available_dimensions(self) -> list[dict[str, Any]]:
        out = []
        for d in DIMENSION_DEFS:
            available = all(self.repo.has_sheet(s) for s in d["requires"])
            out.append({"key": d["key"], "label": d["key"], "path": d["path"], "available": available})
        return out

    # --------------------------------------------------- position-grain frame
    def _positions_enriched(self, position_ids: list[str], as_of_date: str) -> pd.DataFrame:
        pos = self.repo.get("position")
        pos = pos[(pos["positionId"].isin(position_ids)) & (pos["asOfDate"].astype(str) == as_of_date)].copy()
        pos = pos.drop_duplicates(subset=["positionId"])
        instrument = self.repo.get("instrument")[["instrumentId", "instrumentName", "assetClassId", "instrumentType"]]
        pos = pos.merge(instrument, on="instrumentId", how="left")
        return pos

    # ------------------------------------------------------------- dimensions
    def asset_class(self, position_ids: list[str], as_of_date: str) -> dict[str, Any]:
        pos = self._positions_enriched(position_ids, as_of_date)
        ac = self.repo.get("asset_class")[["assetClassId", "assetClassCode", "assetClassName"]]
        pos = pos.merge(ac, on="assetClassId", how="left")
        rows = []
        for name, g in pos.groupby("assetClassName"):
            rows.append(
                {
                    "assetClass": name,
                    "position_count": int(len(g)),
                    "instrument_count": int(g["instrumentId"].nunique()),
                    "market_value_bcy": float(g["marketValueBcy"].sum()),
                }
            )
        return {"label": "Market Value by Asset Class", "grain": "position", "rows": sorted(rows, key=lambda r: -abs(r["market_value_bcy"]))}

    def desk(self, position_ids: list[str], as_of_date: str) -> dict[str, Any]:
        return self._by_reference(position_ids, as_of_date, "deskId", "desk", "deskName", "Market Value by Desk")

    def book(self, position_ids: list[str], as_of_date: str) -> dict[str, Any]:
        return self._by_reference(position_ids, as_of_date, "bookId", "book", "bookName", "Market Value by Book")

    def instrument(self, position_ids: list[str], as_of_date: str) -> dict[str, Any]:
        pos = self._positions_enriched(position_ids, as_of_date)
        rows = []
        for (iid, iname), g in pos.groupby(["instrumentId", "instrumentName"]):
            rows.append(
                {
                    "instrumentId": iid,
                    "instrumentName": iname,
                    "position_count": int(len(g)),
                    "market_value_bcy": float(g["marketValueBcy"].sum()),
                }
            )
        return {"label": "Market Value by Instrument", "grain": "position", "rows": sorted(rows, key=lambda r: -abs(r["market_value_bcy"]))}

    def _by_reference(self, position_ids, as_of_date, id_col, ref_sheet, name_col, label) -> dict[str, Any]:
        pos = self._positions_enriched(position_ids, as_of_date)
        ref = self.repo.get(ref_sheet)
        name_map = dict(zip(ref[id_col.replace(" (FK)", "")], ref[name_col])) if name_col in ref.columns else {}
        rows = []
        for _id, g in pos.groupby(id_col):
            rows.append(
                {
                    "id": _id,
                    "name": name_map.get(_id, _id),
                    "position_count": int(len(g)),
                    "market_value_bcy": float(g["marketValueBcy"].sum()),
                }
            )
        return {"label": label, "grain": "position", "rows": sorted(rows, key=lambda r: -abs(r["market_value_bcy"]))}

    def business(self, portfolio_type: str, exclude_metric_id: str | None = None) -> dict[str, Any]:
        """Business units carrying VaR metrics, with their stored VaR observations.

        `exclude_metric_id` drops the aggregate Trading metric so the stored -$38m
        value (removed from the main VaR result during validation) is not shown here.
        """
        rm = self.repo.get("risk_metric")
        if exclude_metric_id:
            rm = rm[rm["riskMetricId"] != exclude_metric_id]
        bu = self.repo.get("hsbc_global_Business_Unit")
        obs = self.repo.get("risk_metric_mr_obs")
        bu_names = dict(zip(bu["businessUnitId"], bu["hsbcGlobalBusinessFrameworkUnitName"]))

        obs = obs.copy()
        obs["_dt"] = pd.to_datetime(obs["observationDateTime"], errors="coerce")
        latest_val = (
            obs.sort_values("_dt").groupby("riskMetricId").tail(1).set_index("riskMetricId")["metricValue"].to_dict()
        )

        rows = []
        for bu_id, g in rm.groupby("businessUnitId"):
            metric_ids = g["riskMetricId"].tolist()
            metrics = [
                {"riskMetricId": m, "latest_var": float(latest_val[m])}
                for m in metric_ids
                if m in latest_val
            ]
            rows.append(
                {
                    "businessUnitId": bu_id,
                    "businessUnit": bu_names.get(bu_id, bu_id),
                    "metric_count": len(metric_ids),
                    "metrics": metrics,
                }
            )
        return {"label": "VaR Metrics by Business Unit", "rows": sorted(rows, key=lambda r: str(r["businessUnitId"]))}
