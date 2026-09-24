"""Response models. Every numeric fact carries governance metadata."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

NOT_AVAILABLE = "Not available from current data model"
NOT_CALCULABLE = "Not independently calculable from current data model"


class MetricStatus(str, Enum):
    STORED = "STORED"          # retrieved verbatim from the workbook
    CALCULATED = "CALCULATED"  # deterministic Python from workbook data
    REFERENCE = "REFERENCE"    # stored configuration/threshold used as an input, not a result
    UNAVAILABLE = "UNAVAILABLE"  # cannot be derived from the current data model


class Metric(BaseModel):
    """A single governed metric with full traceability."""

    metric_name: str
    value: float | int | None = None
    display: str | None = None          # pre-formatted string for the UI
    unit: str | None = None
    status: MetricStatus
    source: str                          # workbook lineage, e.g. 'risk_metric_mr_obs.metricValue'
    note: str | None = None


class LineageEntry(BaseModel):
    label: str
    source: str
    detail: str | None = None


class ConfigOptions(BaseModel):
    risk_horizons: list[dict[str, Any]]
    portfolio_types: list[dict[str, Any]]
    lookback_periods: list[dict[str, Any]]
    commentary_dimensions: list[dict[str, Any]]
    model_config_summary: dict[str, Any]


class SimulationRequestEcho(BaseModel):
    forward_days: int
    portfolio_type: str
    lookback_days: int
    dimensions: list[str]
    confidence_level: int | None = None
    methodology: str | None = None
    as_of_date: str | None = None


class SimulationResult(BaseModel):
    """The complete deterministic result. This is what the commentary layer summarises."""

    generated_at: str
    simulation_parameters: dict[str, Any]
    portfolio: dict[str, Any]
    simulation: dict[str, Any]  # real-time Historical Simulation VaR (calculated, not stored)
    tail_contribution: dict[str, Any] = Field(default_factory=dict)  # decomposition of the selected VaR-tail P&L
    metrics: list[Metric]
    var_trend: list[dict[str, Any]]
    risk_factors: list[dict[str, Any]]
    historical_movements: dict[str, Any]
    dimension_analysis: dict[str, Any]
    scenario_analysis: dict[str, Any]
    stress_pnl: dict[str, Any]
    sensitivity: list[dict[str, Any]]
    thresholds: dict[str, Any]
    lineage: dict[str, list[LineageEntry]]
    selected_commentary_dimensions: list[str]
    warnings: list[str] = Field(default_factory=list)


class CommentaryResponse(BaseModel):
    commentary: str
    generated_at: str
    model: str
    evidence: dict[str, Any]
    selected_dimensions: list[str]
    source: str  # 'groq' or 'unavailable'
