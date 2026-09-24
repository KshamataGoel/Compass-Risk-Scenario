"""Data lineage / traceability.

Provides, for each displayed metric family, the workbook entities and columns it
derives from — so any figure in the UI can be traced back to the logical model.
"""
from __future__ import annotations

from backend.models.response_models import LineageEntry


class LineageService:
    def lineage(self) -> dict[str, list[LineageEntry]]:
        return {
            "Simulation VaR": [
                LineageEntry(label="Portfolio value history", source="position.asOfDate + position.marketValueBcy", detail="SUM(marketValueBcy) per trading date at position grain"),
                LineageEntry(label="Scope", source="trade.tradingBookFlag", detail="Positions filtered to the selected portfolio type"),
                LineageEntry(label="P&L distribution", source="PortfolioValue(t) - PortfolioValue(t-H)", detail="H = selected risk horizon (trading observations)"),
                LineageEntry(label="VaR", source="ABS(quantile(pnl, 1 - confidence, method='lower'))", detail="Lookback and confidence are user inputs — NOT read from risk_metric_mr / risk_metric_mr_obs"),
            ],
            "Previous Simulation VaR": [
                LineageEntry(label="Value", source="Same calculation, one as-of period earlier", detail="UNAVAILABLE if insufficient history; never substituted with stored VaR"),
            ],
            "VaR Change": [
                LineageEntry(label="Derivation", source="Simulation VaR - Previous Simulation VaR", detail="Both are calculated, not stored"),
            ],
            "Warning Threshold": [
                LineageEntry(label="Value", source="risk_threshold.thresholdValueHigh", detail="Reference input; threshold bound to the aggregate VaR metricId"),
            ],
            "VaR Utilisation": [
                LineageEntry(label="Derivation", source="Simulation VaR / risk_threshold.thresholdValueHigh x 100", detail="Uses the calculated Simulation VaR"),
            ],
            "Portfolio": [
                LineageEntry(label="Scope", source="position + trade", detail="Latest position.asOfDate filtered by trade.tradingBookFlag"),
                LineageEntry(label="Market Value", source="SUM(position.marketValueBcy)", detail="Aggregated at position grain (no double counting)"),
            ],
            "Associated Risk Factors": [
                LineageEntry(label="Exposure", source="instrument_risk_factor_map + risk_factor", detail="position -> instrument -> map -> risk_factor (association, not contribution)"),
                LineageEntry(label="Observations", source="risk_factor_obs", detail="Historical observed values; 1-day movements computed in Python"),
            ],
            "Asset Class": [
                LineageEntry(label="Derivation", source="position -> instrument.assetClassId -> asset_class", detail="Market value by asset class at position grain"),
            ],
            "Business": [
                LineageEntry(label="Derivation", source="risk_metric.businessUnitId -> hsbc_global_Business_Unit", detail="VaR metrics grouped by business unit"),
            ],
            "Scenario": [
                LineageEntry(label="Shocks", source="scenario_mr -> risk_factor_shock -> risk_factor", detail="Explicit stress shocks per risk factor"),
                LineageEntry(label="Scenario P&L", source="risk_pnl_record.amountBaseCcy", detail="Aggregated at position grain"),
            ],
            "Stress Scenario P&L": [
                LineageEntry(label="Value", source="SUM(risk_pnl_record.amountBaseCcy)", detail="Position grain; not VaR"),
            ],
            "Sensitivity": [
                LineageEntry(label="Value", source="sensitivity.sensitivityValue", detail="With sensitivityValueCurrency, associated riskMetricId and riskModelId"),
            ],
        }
