"""Simulation orchestrator.

Composes the deterministic services into a single governed SimulationResult. The
Current/Simulation VaR is CALCULATED at request time by SimulationVarService from
the portfolio's own market-value history — it does NOT read the stored
risk_metric_mr_obs / risk_metric_obs (-$38m) values. Groq is never called here.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

from backend.data.excel_repository import ExcelRepository
from backend.models.response_models import Metric, MetricStatus, NOT_AVAILABLE, SimulationResult
from backend.services.dimension_service import DimensionService
from backend.services.historical_simulation_service import HistoricalSimulationService
from backend.services.lineage_service import LineageService
from backend.services.portfolio_service import PortfolioService
from backend.services.risk_factor_service import RiskFactorService
from backend.services.risk_metric_service import RiskMetricService
from backend.services.scenario_service import ScenarioService
from backend.services.sensitivity_service import SensitivityService
from backend.services.simulation_var_service import SimulationVarService
from backend.services.tail_contribution_service import TailContributionService
from backend.services.threshold_service import ThresholdService


class SimulationOrchestrator:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo
        self.portfolio = PortfolioService(repo)
        self.risk_factor = RiskFactorService(repo)
        self.hist_sim = HistoricalSimulationService(repo)
        self.sim_var = SimulationVarService(repo)
        self.tail_contribution = TailContributionService(repo)
        self.risk_metric = RiskMetricService(repo)  # used only to locate the reference threshold metric
        self.threshold = ThresholdService(repo)
        self.scenario = ScenarioService(repo)
        self.sensitivity = SensitivityService(repo)
        self.dimension = DimensionService(repo)
        self.lineage = LineageService()

    def run(
        self,
        portfolio_type: str,
        forward_horizon_days: int,
        lookback_days: int,
        confidence_level: float,
        dimensions: list[str],
    ) -> SimulationResult:
        warnings: list[str] = []

        # ---- Step 1-2: portfolio scope & current positions.
        portfolio = self.portfolio.get_current_portfolio(portfolio_type)
        if not portfolio.get("available"):
            return self._empty_result(portfolio_type, forward_horizon_days, lookback_days, confidence_level, dimensions, portfolio, warnings)

        as_of = portfolio["as_of_date"]
        instrument_ids = portfolio["instrument_ids"]
        position_ids = portfolio["position_ids"]

        # ---- Real-time Historical Simulation VaR (calculated, not stored).
        sim = self.sim_var.calculate(
            portfolio_type=portfolio_type,
            lookback_days=lookback_days,
            horizon_days=forward_horizon_days,
            confidence_level=confidence_level,
        )
        if not sim.get("available"):
            warnings.append(sim.get("message", "Simulation VaR could not be calculated."))

        unit = sim.get("unit", "USD") if sim.get("available") else (portfolio.get("base_currency") or "USD")

        # ---- VaR Tail Loss Contribution: decompose the selected tail-period P&L.
        tail_contribution: dict = {"available": False}
        tail_period = sim.get("tail_period") if sim.get("available") else None
        if tail_period:
            tail_contribution = self.tail_contribution.contribution(
                portfolio_type, tail_period["start_date"], tail_period["end_date"]
            )
            # Reconciliation guard: the decomposition must equal the selected tail P&L.
            if tail_contribution.get("available"):
                net = tail_contribution.get("net_tail_pnl")
                if net is None or abs(net - tail_period["tail_pnl"]) > 1.0:
                    tail_contribution["reconciled"] = False
                    warnings.append(
                        f"Tail contribution did not reconcile: sum {net} vs selected tail P&L {tail_period['tail_pnl']}."
                    )
        elif sim.get("available"):
            tail_contribution = {"available": False, "message": "No loss tail (Simulation VaR = 0)."}

        # ---- Step 3-4: instruments already resolved; map risk factors.
        risk_factors = self.risk_factor.get_associated_risk_factors(instrument_ids, lookback_days)
        rf_ids = [rf["riskFactorId"] for rf in risk_factors]

        # ---- Step 5-6: historical observations & movements (unchanged area).
        historical = self.hist_sim.historical_movements(rf_ids, lookback_days)

        # ---- Reference warning threshold (INPUT/REFERENCE only; VaR is the calculated one).
        threshold_metric_id = self.risk_metric.aggregate_metric_id(portfolio_type)
        threshold_info = self.threshold.threshold_for(threshold_metric_id) if threshold_metric_id else None
        sim_var_value = sim.get("simulation_var") if sim.get("available") else None
        util = self.threshold.utilisation(threshold_metric_id, sim_var_value) if (threshold_metric_id and sim_var_value is not None) else {"available": False}

        # ---- Metric cards (calculated first; no stored -$38m anywhere).
        metrics = self._build_metric_cards(sim, portfolio, threshold_info, util, unit, len(rf_ids))

        # Scenario count (reference).
        scen_all = self.scenario.scenarios(position_ids=position_ids)
        metrics.append(Metric(metric_name="Scenario Count", value=len(scen_all["scenarios"]), unit="count",
                              status=MetricStatus.CALCULATED, source="COUNT(scenario_mr)"))

        # Stress P&L (kept as a separate stored area, not part of the VaR result).
        scenario_set_id = self._config_scenario_set(threshold_metric_id)
        stress = self.scenario.stress_pnl_summary(scenario_set_id, position_ids)

        # ---- Step 8: dimension analysis (only user-selected & available).
        available_dims = {d["key"] for d in self.dimension.available_dimensions() if d["available"]}
        selected = [d for d in dimensions if d in available_dims] or sorted(available_dims)
        dimension_analysis = self._build_dimensions(selected, portfolio, portfolio_type, risk_factors, historical, scen_all, threshold_metric_id)

        sensitivities = self.sensitivity.sensitivities()

        return SimulationResult(
            generated_at=_now(),
            simulation_parameters={
                "portfolio_type": portfolio_type,
                "forward_horizon_days": forward_horizon_days,
                # Effective observation count actually used (matters when "Full history" (0) is selected).
                "lookback_days": sim.get("lookback_days") if sim.get("available") else lookback_days,
                "lookback_requested": lookback_days,
                "full_history": lookback_days == 0,
                "confidence_level": confidence_level,
                "as_of_date": as_of,
                "methodology": sim.get("methodology") if sim.get("available") else "Historical Simulation",
                "dimensions": selected,
            },
            portfolio=portfolio,
            simulation=sim,
            tail_contribution=tail_contribution,
            metrics=metrics,
            var_trend=[],  # stored VaR trend intentionally removed; see `simulation.pnl_distribution`.
            risk_factors=risk_factors,
            historical_movements=historical,
            dimension_analysis=dimension_analysis,
            scenario_analysis=scen_all,
            stress_pnl=stress,
            sensitivity=sensitivities,
            thresholds={
                "utilisation": util,
                "warning_threshold": threshold_info,
                "breaches": self.threshold.breaches(),
            },
            lineage=self.lineage.lineage(),
            selected_commentary_dimensions=selected,
            warnings=warnings,
        )

    # ------------------------------------------------------------- helpers
    def _build_metric_cards(self, sim, portfolio, threshold_info, util, unit, rf_count) -> list[Metric]:
        cards: list[Metric] = []
        sim_source = "position.marketValueBcy history → lookback → horizon → empirical quantile @ confidence"

        if sim.get("available"):
            cards.append(Metric(metric_name="Simulation VaR", value=sim["simulation_var"], unit=unit,
                                status=MetricStatus.CALCULATED, source=sim_source))
            if sim.get("previous_available"):
                cards.append(Metric(metric_name="Previous Simulation VaR", value=sim["previous_simulation_var"], unit=unit,
                                    status=MetricStatus.CALCULATED, source=sim_source + " (full recalculation, one as-of date earlier)"))
                cards.append(Metric(metric_name="VaR Variance", value=sim["var_variance"], unit=unit,
                                    status=MetricStatus.CALCULATED, source="Simulation VaR - Previous Simulation VaR"))
                cards.append(Metric(metric_name="VaR Variance %", value=sim.get("var_variance_pct"), unit="%",
                                    status=MetricStatus.CALCULATED, source="(Current - Previous) / Previous x 100"))
                cards.append(Metric(metric_name="VaR Trend", value=None, display=sim.get("var_trend_classification"), unit=None,
                                    status=MetricStatus.CALCULATED, source=f"Python classification (|variance| threshold {sim.get('trend_threshold_pct')}%)"))
            else:
                cards.append(Metric(metric_name="Previous Simulation VaR", value=None, unit=unit,
                                    status=MetricStatus.UNAVAILABLE, source="Insufficient history for a prior as-of date",
                                    note="Not substituted with stored VaR."))
        else:
            cards.append(Metric(metric_name="Simulation VaR", value=None, unit=unit,
                                status=MetricStatus.UNAVAILABLE, source=sim_source, note=sim.get("message")))

        if portfolio.get("available"):
            cards.append(Metric(metric_name="Portfolio Market Value", value=portfolio["total_market_value_bcy"], unit=unit,
                                status=MetricStatus.CALCULATED, source="SUM(position.marketValueBcy) at position grain"))
            cards.append(Metric(metric_name="Position Count", value=portfolio["position_count"], unit="count",
                                status=MetricStatus.CALCULATED, source="COUNT(position) at latest asOfDate"))
            cards.append(Metric(metric_name="Trade Count", value=portfolio["trade_count"], unit="count",
                                status=MetricStatus.CALCULATED, source="DISTINCT(position.tradeId)"))
            cards.append(Metric(metric_name="Instrument Count", value=portfolio["instrument_count"], unit="count",
                                status=MetricStatus.CALCULATED, source="DISTINCT(position.instrumentId)"))

        if threshold_info:
            cards.append(Metric(metric_name="Warning Threshold", value=threshold_info["warning_threshold"], unit=unit,
                                status=MetricStatus.REFERENCE, source="risk_threshold.thresholdValueHigh (reference input)"))
        if util.get("available"):
            cards.append(Metric(metric_name="VaR Utilisation", value=util["utilisation_pct"], unit="%",
                                status=MetricStatus.CALCULATED, source="Simulation VaR / Warning Threshold x 100"))

        if sim.get("available"):
            cards.append(Metric(metric_name="Worst Historical P&L", value=sim["worst_pnl"], unit=unit,
                                status=MetricStatus.CALCULATED, source="MIN(historical_pnl) over the P&L distribution"))
            cards.append(Metric(metric_name="Best Historical P&L", value=sim["best_pnl"], unit=unit,
                                status=MetricStatus.CALCULATED, source="MAX(historical_pnl)"))
            cards.append(Metric(metric_name="Average Historical P&L", value=sim["average_pnl"], unit=unit,
                                status=MetricStatus.CALCULATED, source="MEAN(historical_pnl)"))
            cards.append(Metric(metric_name="P&L Observation Count", value=sim["observation_count"], unit="count",
                                status=MetricStatus.CALCULATED, source="COUNT(historical_pnl)"))

        cards.append(Metric(metric_name="Risk Factor Count", value=rf_count, unit="count",
                            status=MetricStatus.CALCULATED, source="DISTINCT associated risk factors via instrument_risk_factor_map"))
        return cards

    def _config_scenario_set(self, metric_id: str | None) -> str | None:
        if metric_id is None:
            return None
        cfg = self.risk_metric.config_for(metric_id)
        return cfg.get("scenarioSetId")

    def _build_dimensions(self, selected, portfolio, portfolio_type, risk_factors, historical, scen_all, aggregate_metric_id) -> dict[str, Any]:
        as_of = portfolio["as_of_date"]
        pids = portfolio["position_ids"]
        out: dict[str, Any] = {}
        for dim in selected:
            if dim == "Asset Class":
                out[dim] = self.dimension.asset_class(pids, as_of)
            elif dim == "Desk":
                out[dim] = self.dimension.desk(pids, as_of)
            elif dim == "Book":
                out[dim] = self.dimension.book(pids, as_of)
            elif dim == "Instrument":
                out[dim] = self.dimension.instrument(pids, as_of)
            elif dim == "Business":
                # Exclude the aggregate Trading metric so the removed stored VaR never reappears.
                out[dim] = self.dimension.business(portfolio_type, exclude_metric_id=aggregate_metric_id)
            elif dim == "Risk Factor":
                out[dim] = {"label": "Associated Risk Factors", "rows": risk_factors, "movements": historical.get("factors", [])}
            elif dim == "Scenario":
                out[dim] = scen_all
        return out

    def _empty_result(self, portfolio_type, forward_horizon_days, lookback_days, confidence_level, dimensions, portfolio, warnings) -> SimulationResult:
        return SimulationResult(
            generated_at=_now(),
            simulation_parameters={
                "portfolio_type": portfolio_type,
                "forward_horizon_days": forward_horizon_days,
                "lookback_days": lookback_days,
                "confidence_level": confidence_level,
                "message": portfolio.get("message"),
            },
            portfolio=portfolio,
            simulation={"available": False, "message": portfolio.get("message", NOT_AVAILABLE)},
            metrics=[],
            var_trend=[],
            risk_factors=[],
            historical_movements={},
            dimension_analysis={},
            scenario_analysis={},
            stress_pnl={},
            sensitivity=[],
            thresholds={},
            lineage=self.lineage.lineage(),
            selected_commentary_dimensions=dimensions,
            warnings=warnings + [portfolio.get("message", "No data for selected scope.")],
        )


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()
