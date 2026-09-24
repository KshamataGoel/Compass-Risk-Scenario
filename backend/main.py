"""FastAPI application entry point.

Endpoints:
  GET  /api/health              liveness
  GET  /api/data-health         workbook validation & health report
  GET  /api/config/options      valid simulation selections (derived from workbook)
  POST /api/simulation          deterministic simulation result (NO LLM)
  GET  /api/metrics             aggregate VaR metrics for a portfolio type
  GET  /api/risk-factors        associated risk factors
  GET  /api/scenarios           scenario dimension
  POST /api/commentary          management commentary (Groq — language layer only)
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.data.excel_repository import get_repository
from backend.data.schema_validator import data_health
from backend.models.request_models import (
    CommentaryRequest,
    ORCommentaryRequest,
    OperationalResilienceRequest,
    ParseParametersRequest,
    RouteRequest,
    SaveSimulationRequest,
    SimulationRequest,
)
from backend.services.commentary_service import CommentaryService
from backend.services.config_service import ConfigService
from backend.services.output_service import OutputService
from backend.services.parameter_parser_service import ParameterParserService
from backend.services.risk_stripe_router import RiskStripeRouter
from backend.services.operational_resilience.or_commentary_service import ORCommentaryService
from backend.services.operational_resilience.or_orchestrator import OROrchestrator
from backend.services.operational_resilience.or_repository import get_or_repository
from backend.services.operational_resilience.scenario_service import ScenarioService as ORScenarioService
from backend.services.portfolio_service import PortfolioService
from backend.services.risk_factor_service import RiskFactorService
from backend.services.scenario_service import ScenarioService
from backend.services.simulation_orchestrator import SimulationOrchestrator
from backend.services.simulation_var_service import SimulationVarService

# Debug logging for step-by-step VaR validation (see the "simulation" logger).
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

settings = get_settings()
app = FastAPI(title="Market Risk Scenario Simulation", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    # Load & validate both risk-stripe workbooks once at startup.
    get_repository(settings.excel_path)
    try:
        get_or_repository(settings.or_excel_path)
    except Exception:  # noqa: BLE001 - OR workbook optional; MR path must still start.
        pass


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "groq_configured": settings.groq_configured, "model": settings.groq_model}


@app.get("/api/data-health")
def api_data_health() -> dict:
    return data_health(get_repository())


@app.get("/api/config/options")
def config_options() -> dict:
    return ConfigService(get_repository()).options()


@app.post("/api/simulation")
def run_simulation(req: SimulationRequest) -> dict:
    repo = get_repository()
    orchestrator = SimulationOrchestrator(repo)
    result = orchestrator.run(
        portfolio_type=req.portfolio_type,
        forward_horizon_days=req.forward_horizon_days,
        lookback_days=req.lookback_days,
        confidence_level=req.confidence_level,
        dimensions=req.dimensions,
    )
    return result.model_dump()


@app.get("/api/metrics")
def metrics(
    portfolio_type: str = Query("Trading"),
    forward_horizon_days: int = Query(1),
    lookback_days: int = Query(10),
    confidence_level: float = Query(99),
) -> dict:
    # Real-time calculated VaR (no stored -$38m dependency).
    repo = get_repository()
    return SimulationVarService(repo).calculate(
        portfolio_type=portfolio_type,
        lookback_days=lookback_days,
        horizon_days=forward_horizon_days,
        confidence_level=confidence_level,
    )


@app.get("/api/risk-factors")
def risk_factors(portfolio_type: str = Query("Trading"), lookback_days: int = Query(10)) -> dict:
    repo = get_repository()
    portfolio = PortfolioService(repo).get_current_portfolio(portfolio_type)
    if not portfolio.get("available"):
        return {"available": False, "message": portfolio.get("message")}
    factors = RiskFactorService(repo).get_associated_risk_factors(portfolio["instrument_ids"], lookback_days)
    return {"available": True, "as_of_date": portfolio["as_of_date"], "risk_factors": factors}


@app.get("/api/scenarios")
def scenarios(portfolio_type: str = Query("Trading")) -> dict:
    repo = get_repository()
    portfolio = PortfolioService(repo).get_current_portfolio(portfolio_type)
    position_ids = portfolio.get("position_ids") if portfolio.get("available") else None
    return ScenarioService(repo).scenarios(position_ids=position_ids)


@app.post("/api/commentary")
def commentary(req: CommentaryRequest) -> dict:
    if not req.simulation_result:
        raise HTTPException(status_code=400, detail="simulation_result is required.")
    service = CommentaryService(settings)
    return service.generate(req.simulation_result)


@app.post("/api/route")
def route(req: RouteRequest) -> dict:
    # Risk-stripe classification (LLM classifier + deterministic fallback). No metrics computed.
    return RiskStripeRouter(settings).classify(req.text)


@app.get("/api/or/scenarios")
def or_scenarios() -> dict:
    return {"scenarios": ORScenarioService(get_or_repository()).all_scenarios()}


@app.post("/api/operational-resilience")
def operational_resilience(req: OperationalResilienceRequest) -> dict:
    # Operational Resilience engine: deterministic, from the OR workbook only.
    orch = OROrchestrator(get_or_repository())
    return orch.run(req.text, scenario_id=req.scenario_id, requested_dimensions=req.requested_dimensions)


@app.post("/api/or-commentary")
def or_commentary(req: ORCommentaryRequest) -> dict:
    if not req.or_result:
        raise HTTPException(status_code=400, detail="or_result is required.")
    return ORCommentaryService(settings).generate(req.or_result)


@app.post("/api/parse-parameters")
def parse_parameters(req: ParseParametersRequest) -> dict:
    # Parameter-parser LLM role: natural language -> validated simulation parameters.
    # Never blocks the simulation; on failure the resolved values fall back to defaults.
    service = ParameterParserService(settings, get_repository())
    return service.parse_and_resolve(req.text, req.current)


@app.post("/api/save-simulation")
def save_simulation(req: SaveSimulationRequest) -> dict:
    # Persists only the calculated simulation result (never the stored source VaR).
    if not req.simulation_result:
        raise HTTPException(status_code=400, detail="simulation_result is required.")
    return OutputService(settings.simulation_output_path).save_simulation(req.simulation_result)


@app.get("/api/saved-simulations")
def saved_simulations() -> dict:
    return OutputService(settings.simulation_output_path).list_runs()
