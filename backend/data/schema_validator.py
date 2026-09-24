"""Schema validation & data-health reporting.

Validates that the sheets and columns the deterministic services rely on are
present. Reports missing dependencies rather than silently substituting data.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository

# Sheet -> columns the application depends on (clean names, post ' (FK)' strip).
REQUIRED: dict[str, list[str]] = {
    "position": ["positionId", "asOfDate", "bookId", "tradeId", "instrumentId", "deskId", "marketValueBcy"],
    "trade": ["tradeId", "tradingBookFlag", "instrumentId", "bookId", "deskId"],
    "instrument": ["instrumentId", "instrumentName", "assetClassId"],
    "asset_class": ["assetClassId", "assetClassCode", "assetClassName"],
    "risk_factor": ["riskFactorId", "riskFactorName", "riskFactorType", "quoteCurrency"],
    "risk_factor_obs": ["riskFactorObsId", "riskFactorId", "observationDate", "observedValue", "observationUnit"],
    "instrument_risk_factor_map": ["instrumentId", "riskFactorId"],
    "risk_metric": ["riskMetricId", "partyIdentifier", "businessUnitId", "riskIdentifier", "riskMeasureId"],
    "risk_metric_mr": ["riskMetricId", "confidenceLevel", "timeHorizonDays", "calculationWindowDays", "methodology", "scenarioSetId"],
    "risk_metric_mr_obs": ["riskMetricMrObsId", "riskMetricId", "observationDateTime", "metricValue"],
    "risk_threshold": ["thresholdId", "riskMetricId", "thresholdValueHigh"],
    "risk": ["riskIdentifier", "riskTypeId", "businessUnitId", "portfolioId"],
    "scenario_mr": ["scenarioSetId", "scenarioSetName", "scenarioType"],
    "risk_factor_shock": ["scenarioSetId", "riskFactorId", "shockType", "shockValue", "shockUnit"],
    "risk_pnl_record": ["riskPnlRecordId", "positionId", "scenarioSetId", "amountBaseCcy", "pnlComponent"],
    "sensitivity": ["sensitivityId", "riskMetricId", "sensitivityValue", "sensitivityValueCurrency"],
    "hsbc_global_Business_Unit": ["businessUnitId", "hsbcGlobalBusinessFrameworkUnitName"],
    "desk": ["deskId", "deskName"],
    "book": ["bookId", "bookName"],
}

# Relationship checks: (child sheet, child col) must be a subset of (parent sheet, parent col).
RELATIONSHIPS: list[tuple[str, str, str, str]] = [
    ("position", "tradeId", "trade", "tradeId"),
    ("position", "instrumentId", "instrument", "instrumentId"),
    ("position", "bookId", "book", "bookId"),
    ("position", "deskId", "desk", "deskId"),
    ("instrument", "assetClassId", "asset_class", "assetClassId"),
    ("instrument_risk_factor_map", "instrumentId", "instrument", "instrumentId"),
    ("instrument_risk_factor_map", "riskFactorId", "risk_factor", "riskFactorId"),
    ("risk_factor_obs", "riskFactorId", "risk_factor", "riskFactorId"),
    ("risk_metric_mr_obs", "riskMetricId", "risk_metric", "riskMetricId"),
    ("risk_threshold", "riskMetricId", "risk_metric", "riskMetricId"),
    ("risk_factor_shock", "scenarioSetId", "scenario_mr", "scenarioSetId"),
]


def validate_schema(repo: ExcelRepository) -> dict[str, Any]:
    missing_sheets: list[str] = []
    missing_columns: dict[str, list[str]] = {}

    for sheet, cols in REQUIRED.items():
        if not repo.has_sheet(sheet):
            missing_sheets.append(sheet)
            continue
        present = set(repo.columns(sheet))
        absent = [c for c in cols if c not in present]
        if absent:
            missing_columns[sheet] = absent

    relationship_issues: list[dict[str, Any]] = []
    for child_s, child_c, parent_s, parent_c in RELATIONSHIPS:
        if not (repo.has_sheet(child_s) and repo.has_sheet(parent_s)):
            continue
        child = repo.get(child_s)
        parent = repo.get(parent_s)
        if child_c not in child.columns or parent_c not in parent.columns:
            continue
        child_vals = set(child[child_c].dropna().unique())
        parent_vals = set(parent[parent_c].dropna().unique())
        orphans = sorted(str(v) for v in (child_vals - parent_vals))
        if orphans:
            relationship_issues.append(
                {"relationship": f"{child_s}.{child_c} -> {parent_s}.{parent_c}", "orphans": orphans}
            )

    return {
        "missing_sheets": missing_sheets,
        "missing_columns": missing_columns,
        "relationship_issues": relationship_issues,
        "valid": not missing_sheets and not missing_columns and not relationship_issues,
    }


def data_health(repo: ExcelRepository) -> dict[str, Any]:
    """Full health report for GET /api/data-health."""
    sheets_info = []
    for name in repo.sheet_names:
        df = repo.get(name)
        sheets_info.append(
            {
                "sheet": name,
                "rows": len(df),
                "columns": list(df.columns),
                "original_columns": repo.original_columns(name),
            }
        )

    # Latest dates & historical observation range.
    latest_position = repo.latest_value("position", "asOfDate")
    obs = repo.get("risk_factor_obs", required=False)
    obs_range: dict[str, Any] = {}
    if obs is not None and "observationDate" in obs.columns:
        dates = pd.to_datetime(obs["observationDate"], errors="coerce").dropna()
        obs_range = {
            "min": str(dates.min().date()) if not dates.empty else None,
            "max": str(dates.max().date()) if not dates.empty else None,
            "trading_days": int(dates.dt.date.nunique()) if not dates.empty else 0,
        }
    latest_var = repo.latest_value("risk_metric_mr_obs", "observationDateTime")

    return {
        "workbook": str(repo.excel_path),
        "sheet_count": len(repo.sheet_names),
        "sheets": sheets_info,
        "validation": validate_schema(repo),
        "latest_position_date": str(latest_position.date()) if latest_position is not None and pd.notna(latest_position) else None,
        "latest_var_observation": str(latest_var) if latest_var is not None and pd.notna(latest_var) else None,
        "historical_observation_range": obs_range,
    }
