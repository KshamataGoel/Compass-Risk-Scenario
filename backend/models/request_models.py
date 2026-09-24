"""Request models for the API."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class SimulationRequest(BaseModel):
    """Parameters for the real-time Historical Simulation VaR.

    All four drivers are genuine user inputs. The backend uses THESE values, never
    the stored risk_metric_mr configuration.
    """

    portfolio_type: str = Field("Trading", description="Derived from trade.tradingBookFlag.")
    forward_horizon_days: int = Field(1, ge=1, description="Risk horizon H in trading days.")
    lookback_days: int = Field(5, ge=0, description="Historical P&L lookback = number of P&L observations (N). 0 = full history (all available observations for the horizon).")
    confidence_level: float = Field(99, gt=0, lt=100, description="Confidence level, e.g. 99 or 95.")
    dimensions: list[str] = Field(default_factory=list, description="Selected commentary dimensions.")

    # Backward-compatible alias: accept the old 'forward_days' too.
    @model_validator(mode="before")
    @classmethod
    def _alias(cls, data):
        if isinstance(data, dict) and "forward_horizon_days" not in data and "forward_days" in data:
            data["forward_horizon_days"] = data["forward_days"]
        return data


class CommentaryRequest(BaseModel):
    """The already-validated deterministic simulation result is echoed back for commentary.

    The commentary endpoint never re-reads or invents data; it only summarises this payload.
    """

    simulation_result: dict


class ParseParametersRequest(BaseModel):
    """Natural-language simulation instruction + the current control values.

    Groq extracts explicit parameters; Python validates and fills gaps from `current`.
    """

    text: str = Field("", description="Natural-language simulation request.")
    current: dict = Field(default_factory=dict, description="Current dropdown/default values used to fill omitted parameters.")


class RouteRequest(BaseModel):
    """Natural-language request to classify into a risk stripe."""

    text: str = Field("", description="The user's natural-language request.")


class OperationalResilienceRequest(BaseModel):
    """Run the Operational Resilience engine for a natural-language request."""

    text: str = Field("", description="Natural-language request (scenario resolved from this).")
    scenario_id: str | None = Field(None, description="Optional explicit scenario id (e.g. SCN001).")
    requested_dimensions: list[str] | None = Field(None, description="Optional subset of supported OR dimensions.")


class ORCommentaryRequest(BaseModel):
    """The already-calculated Operational Resilience result, echoed for commentary."""

    or_result: dict


class SaveSimulationRequest(BaseModel):
    """Persist an already-calculated simulation result to the output workbook.

    Only the calculated `simulation` block is written — never the stored source VaR.
    """

    simulation_result: dict
