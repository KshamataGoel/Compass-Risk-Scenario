"""Governance & correctness tests.

The overriding principle under test: no value appears in an API response unless it
can be traced to workbook data or a deterministic calculation from workbook data.
"""
from __future__ import annotations

import pytest

from backend.data.excel_repository import get_repository
from backend.data.schema_validator import data_health, validate_schema
from backend.services.commentary_service import CommentaryService
from backend.config import get_settings
from backend.services.config_service import ConfigService
from backend.services.dimension_service import DimensionService
from backend.services.historical_simulation_service import HistoricalSimulationService
from backend.services.portfolio_service import PortfolioService
from backend.services.risk_factor_service import RiskFactorService
from backend.services.risk_metric_service import RiskMetricService
from backend.services.scenario_service import ScenarioService
from backend.services.simulation_orchestrator import SimulationOrchestrator
from backend.services.simulation_var_service import SimulationVarService
from backend.services.threshold_service import ThresholdService


@pytest.fixture(scope="module")
def repo():
    return get_repository()


# ------------------------------------------------------------- Excel loading
def test_excel_loads_and_fk_columns_normalised(repo):
    assert len(repo.sheet_names) == 28
    # ' (FK)' suffix stripped: position exposes clean 'tradeId', not 'tradeId (FK)'.
    cols = repo.columns("position")
    assert "tradeId" in cols and "tradeId (FK)" not in cols
    # Original headers retained for lineage.
    assert any("(FK)" in c for c in repo.original_columns("position"))


def test_schema_valid(repo):
    result = validate_schema(repo)
    assert result["missing_sheets"] == []
    assert result["missing_columns"] == {}


def test_data_health_reports_range(repo):
    health = data_health(repo)
    assert health["latest_position_date"] == "2026-08-27"
    assert health["historical_observation_range"]["trading_days"] == 10


# ---------------------------------------------------- latest-position selection
def test_latest_position_snapshot(repo):
    p = PortfolioService(repo).get_current_portfolio("Trading")
    assert p["available"] is True
    assert p["as_of_date"] == "2026-08-27"
    assert p["position_count"] == 10
    assert p["trade_count"] == 10
    assert p["instrument_count"] == 5


# ---------------------------------------------------------- trading-book filter
def test_non_trading_unavailable(repo):
    types = {t["label"]: t for t in PortfolioService(repo).available_portfolio_types()}
    assert types["Trading"]["available"] is True
    assert types["Non-Trading"]["available"] is False
    nt = PortfolioService(repo).get_current_portfolio("Non-Trading")
    assert nt["available"] is False


# ------------------------------------------------------------- risk-factor map
def test_risk_factor_mapping(repo):
    p = PortfolioService(repo).get_current_portfolio("Trading")
    factors = RiskFactorService(repo).get_associated_risk_factors(p["instrument_ids"], 10)
    ids = {f["riskFactorId"] for f in factors}
    # 5 instruments map to 7 distinct risk factors.
    assert len(ids) == 7


# ------------------------------------------------ historical ordering & movements
def test_ir_movement_in_bps(repo):
    # RF001 USD 10Y: 4.34 -> 4.38 on the first step == +4 bps.
    hist = HistoricalSimulationService(repo).historical_movements(["RF001"], 10)
    f = hist["factors"][0]
    assert f["basis"] == "bps"
    first = f["movements"][0]
    assert first["previous_value"] == 4.34 and first["current_value"] == 4.38
    assert round(first["movement"], 2) == 4.0


def test_fx_movement_in_pct(repo):
    hist = HistoricalSimulationService(repo).historical_movements(["RF005"], 10)
    f = hist["factors"][0]
    assert f["basis"] == "%"
    m = f["movements"][0]
    expected = (m["current_value"] / m["previous_value"] - 1) * 100
    assert abs(m["movement"] - round(expected, 6)) < 1e-6


def test_full_revaluation_marked_unavailable(repo):
    hist = HistoricalSimulationService(repo).historical_movements(["RF001"], 10)
    assert hist["full_revaluation"]["status"] == "UNAVAILABLE"


# ------------------------------------- real-time Simulation VaR (calculated, not stored)
def test_simulation_var_is_calculated_not_stored(repo):
    svc = SimulationVarService(repo)
    res = svc.calculate("Trading", lookback_days=2, horizon_days=1, confidence_level=98)
    assert res["available"] is True
    # Must NOT be the stored -$38m RMT001 value.
    assert abs(res["simulation_var"] - 38000000) > 1
    assert res["simulation_var"] == 157920
    assert res["observation_count"] == 2


def test_simulation_var_independent_of_stored_rmt001(repo, monkeypatch):
    """Zeroing the stored RMT001 VaR must not change the calculated result."""
    svc = SimulationVarService(repo)
    before = svc.calculate("Trading", lookback_days=2, horizon_days=1, confidence_level=98)["simulation_var"]

    original_get = repo.get

    def patched_get(name, required=True):
        df = original_get(name, required=required)
        if df is not None and name in ("risk_metric_mr_obs", "risk_metric_obs") and "metricValue" in df.columns:
            df = df.copy()
            df["metricValue"] = 0  # obliterate the stored -$38m
        return df

    monkeypatch.setattr(repo, "get", patched_get)
    after = SimulationVarService(repo).calculate("Trading", lookback_days=2, horizon_days=1, confidence_level=98)["simulation_var"]
    assert before == after


# --------------------------------------- FIX 1: lookback = number of P&L observations
def test_lookback_is_observation_count(repo):
    svc = SimulationVarService(repo)
    res = svc.calculate("Trading", lookback_days=2, horizon_days=1, confidence_level=98)
    # N=2 observations require 3 valuation dates (25/26/27 Aug).
    assert res["observation_count"] == 2
    rows = res["pnl_distribution"]
    assert (rows[0]["start_date"], rows[0]["end_date"], rows[0]["historical_pnl"]) == ("2026-08-25", "2026-08-26", -157920)
    assert (rows[1]["start_date"], rows[1]["end_date"], rows[1]["historical_pnl"]) == ("2026-08-26", "2026-08-27", 394800)
    assert res["worst_pnl"] == -157920 and res["best_pnl"] == 394800 and res["average_pnl"] == 118440


# --------------------------------------- FIX 2: VaR = max(0, -lower_tail), never abs(gain)
def test_var_formula_max_zero_on_positive_tail(repo):
    svc = SimulationVarService(repo)
    res = svc.calculate("Trading", lookback_days=2, horizon_days=1, confidence_level=98)
    # The 20-Aug window has only gains -> VaR must be 0 (abs() would wrongly give a positive loss).
    by_date = {p["as_of_date"]: p["simulation_var"] for p in res["var_trend"]}
    assert by_date["2026-08-20"] == 0
    # The selected tail must be the loss observation, not the gain.
    assert res["tail_period"] == {"start_date": "2026-08-25", "end_date": "2026-08-26", "tail_pnl": -157920}


# --------------------------------------- FIX 3: variance, variance %, trend, 6-day series
def test_var_variance_and_trend(repo):
    svc = SimulationVarService(repo)
    res = svc.calculate("Trading", lookback_days=2, horizon_days=1, confidence_level=98)
    assert res["simulation_var"] == 157920
    assert res["previous_simulation_var"] == 473760
    assert res["var_variance"] == -315840
    assert res["var_variance_pct"] == -66.67
    assert res["var_trend_classification"] == "Decreased"
    trend = {p["as_of_date"]: p["simulation_var"] for p in res["var_trend"]}
    assert trend == {
        "2026-08-20": 0, "2026-08-21": 631680, "2026-08-24": 631680,
        "2026-08-25": 473760, "2026-08-26": 473760, "2026-08-27": 157920,
    }


def test_variance_pct_null_on_zero_previous():
    from backend.services.simulation_var_service import _variance_pct, _classify
    assert _variance_pct(100, 0) is None
    assert _classify(None, 631680) == "Increased"
    assert _classify(0.0, 0.0) == "Steady"


def test_previous_var_availability(repo):
    svc = SimulationVarService(repo)
    assert svc.calculate("Trading", lookback_days=2, horizon_days=1, confidence_level=98)["previous_available"] is True
    # N=9 needs 10 dates for current and 11 for previous -> previous unavailable.
    assert svc.calculate("Trading", lookback_days=9, horizon_days=1, confidence_level=99)["previous_available"] is False


def test_insufficient_history(repo):
    svc = SimulationVarService(repo)
    res = svc.calculate("Trading", lookback_days=25, horizon_days=1, confidence_level=99)
    assert res["available"] is False
    assert res["message"] == "Insufficient historical data."


def test_full_history_lookback_sentinel(repo):
    # lookback 0 = full history: uses every available observation for the horizon.
    svc = SimulationVarService(repo)
    r1 = svc.calculate("Trading", lookback_days=0, horizon_days=1, confidence_level=99)
    assert r1["available"] is True and r1["observation_count"] == 9   # 10 dates, H=1
    r2 = svc.calculate("Trading", lookback_days=0, horizon_days=2, confidence_level=99)
    assert r2["observation_count"] == 8                               # 10 dates, H=2
    # Config offers the full-history option keyed to the ~2-week span.
    from backend.services.config_service import ConfigService
    labels = [o["label"] for o in ConfigService(repo).options()["lookback_periods"]]
    assert any("Full history" in l for l in labels)


# --------------------------------------- FIX 4: VaR tail loss contribution reconciles
def test_tail_contribution_reconciles(repo):
    from backend.services.tail_contribution_service import TailContributionService
    tc = TailContributionService(repo).contribution("Trading", "2026-08-25", "2026-08-26")
    assert tc["available"] is True
    assert tc["net_tail_pnl"] == -157920
    assert round(sum(p["tail_pnl"] for p in tc["positions"]), 2) == -157920
    by = {e["exposure"]: e for e in tc["by_exposure"]}
    assert by["XAU Curve"]["tail_pnl"] == -136000 and by["XAU Curve"]["share_pct"] == 86.1
    assert by["EUR/USD"]["classification"] == "Loss offset"
    ac = {a["exposure"]: a["tail_pnl"] for a in tc["by_asset_class"]}
    assert ac["Precious Metals"] == -136000 and ac["Interest Rate"] == -25520 and ac["Foreign Exchange"] == 3600
    assert tc["main_tail_loss_driver"] == "XAU Curve" and tc["main_tail_loss_amount"] == -136000


def test_var_utilisation_uses_simulation_var(repo):
    svc = SimulationVarService(repo)
    sim = svc.calculate("Trading", lookback_days=2, horizon_days=1, confidence_level=98)
    rm = RiskMetricService(repo)
    metric_id = rm.aggregate_metric_id("Trading")
    util = ThresholdService(repo).utilisation(metric_id, sim["simulation_var"])
    assert util["warning_threshold"] == 105555556
    expected = round(sim["simulation_var"] / 105555556 * 100, 2)
    assert util["utilisation_pct"] == expected
    assert util["utilisation_pct"] != 36.0


# ------------------------------------------------------ scenario / no double count
def test_scenario_pnl_position_grain(repo):
    p = PortfolioService(repo).get_current_portfolio("Trading")
    stress = ScenarioService(repo).stress_pnl_summary("SCSET001", p["position_ids"])
    assert stress["available"] is True
    assert stress["total_pnl"] == -11100000
    # 10 positions -> 10 records, no duplication.
    assert stress["record_count"] == 10


def test_scenario_without_pnl_unavailable(repo):
    p = PortfolioService(repo).get_current_portfolio("Trading")
    scen = ScenarioService(repo).scenarios(position_ids=p["position_ids"])
    by_id = {s["scenarioSetId"]: s for s in scen["scenarios"]}
    assert by_id["SCSET001"]["scenario_pnl"]["available"] is True
    # SCSET002 / SCSET003 have shocks but no P&L records.
    assert by_id["SCSET002"]["scenario_pnl"]["available"] is False


def test_no_double_counting_market_value(repo):
    # Total MV must equal the sum over the 10 latest positions, not inflated by RF mapping.
    p = PortfolioService(repo).get_current_portfolio("Trading")
    assert p["total_market_value_bcy"] == 78960000


# ------------------------------------------------------------- dimension filter
def test_dimension_filtering(repo):
    orch = SimulationOrchestrator(repo)
    res = orch.run("Trading", 1, 5, 99, ["Asset Class"]).model_dump()
    assert set(res["dimension_analysis"].keys()) == {"Asset Class"}


def test_asset_class_at_position_grain(repo):
    p = PortfolioService(repo).get_current_portfolio("Trading")
    ac = DimensionService(repo).asset_class(p["position_ids"], p["as_of_date"])
    total = sum(r["market_value_bcy"] for r in ac["rows"])
    assert total == 78960000  # same as portfolio total -> no double count


# --------------------------------------------- orchestrator uses request params, not stored config
def test_orchestrator_var_calculated_and_not_38m(repo):
    res = SimulationOrchestrator(repo).run("Trading", 1, 2, 98, []).model_dump()
    cards = {m["metric_name"]: m for m in res["metrics"]}
    assert "Simulation VaR" in cards
    assert cards["Simulation VaR"]["status"] == "CALCULATED"
    assert cards["Simulation VaR"]["value"] == 157920
    # No card anywhere equals the stored -$38m.
    assert all(abs((m["value"] or 0) - 38000000) > 1 and abs((m["value"] or 0) + 38000000) > 1 for m in res["metrics"])
    assert res["simulation"]["available"] is True
    # Tail contribution wired into the orchestrator result and reconciled.
    assert res["tail_contribution"]["net_tail_pnl"] == -157920
    assert res["tail_contribution"]["main_tail_loss_driver"] == "XAU Curve"


# --------------------------------------------------------- Groq payload construction
def test_commentary_brief_inputs(repo):
    # Scenario NOT selected -> no scenario context in the concise brief.
    res = SimulationOrchestrator(repo).run("Trading", 1, 2, 98, ["Asset Class"]).model_dump()
    evidence = CommentaryService(get_settings()).build_evidence(res)
    brief = evidence["management_brief_inputs"]
    # All figures are pre-calculated, pre-formatted, and traceable — none is the stored -$38m.
    assert brief["risk_horizon"] == "1-day" and brief["portfolio_type"] == "Trading"
    assert brief["var_trend"] == "Decreased"
    assert brief["current_var"] == "$157.9k" and brief["previous_var"] == "$473.8k"
    assert brief["variance_pct_abs"] == "66.7%"
    assert brief["main_tail_driver"] == "XAU Curve" and brief["main_tail_amount"] == "$136.0k"
    assert brief["main_tail_share"] == "86.1%"
    # Secondary loss contributors and the offset are named (not enumerated %s).
    assert "EUR/USD" in brief["offsets"]
    assert set(brief["secondary_loss_contributors"]) == {"GBP Rates", "EUR Rates", "USD Rates"}
    # Scenario context omitted because Scenario was not a selected dimension.
    assert brief["scenario_context"] is None
    # Raw calculated VaR retained for audit; no stored -$38m, no metrics/dimension dump.
    assert evidence["simulation_var"]["current_var"] == 157920
    assert "metrics" not in evidence and "dimension_analysis" not in evidence


def test_commentary_trend_series_pattern(repo):
    # Validation series [0,631680,631680,473760,473760,157920] with current Decreased
    # -> downward pattern, with the recent peak ($631.7k) offered as one earlier reference.
    res = SimulationOrchestrator(repo).run("Trading", 1, 2, 98, ["Asset Class"]).model_dump()
    brief = CommentaryService(get_settings()).build_evidence(res)["management_brief_inputs"]
    assert brief["var_trend_pattern"] == "continuing_downward"
    assert brief["var_trend_phrase"] == "continuing the recent downward trend"
    assert brief["earlier_var_reference"]["value"] == "$631.7k"


def test_trend_pattern_conflict_returns_current_only():
    from backend.services.commentary_service import _trend_pattern
    # Recent series generally rising, but current step Decreased -> no broader-trend claim.
    series = [
        {"as_of_date": "d1", "simulation_var": 100, "trend": None},
        {"as_of_date": "d2", "simulation_var": 200, "trend": "Increased"},
        {"as_of_date": "d3", "simulation_var": 300, "trend": "Increased"},
        {"as_of_date": "d4", "simulation_var": 280, "trend": "Decreased"},
    ]
    assert _trend_pattern(series, "Decreased")["pattern"] == "current_only"
    # Consistent decline confirms downward.
    down = [
        {"as_of_date": "d1", "simulation_var": 300, "trend": None},
        {"as_of_date": "d2", "simulation_var": 250, "trend": "Decreased"},
        {"as_of_date": "d3", "simulation_var": 200, "trend": "Decreased"},
    ]
    assert _trend_pattern(down, "Decreased")["pattern"] == "continuing_downward"


def test_commentary_scenario_context_gated(repo):
    # Scenario selected -> scenario context (name + stress loss) is included.
    res = SimulationOrchestrator(repo).run("Trading", 1, 2, 98, ["Scenario"]).model_dump()
    brief = CommentaryService(get_settings()).build_evidence(res)["management_brief_inputs"]
    ctx = brief["scenario_context"]
    assert ctx is not None
    assert ctx["stress_loss"] == "-$11.1m"
    assert "Rising Long-Term Rates" in (ctx["scenario_name"] or "")


def test_commentary_unavailable_without_key(repo, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "groq_api_key", None)
    res = SimulationOrchestrator(repo).run("Trading", 1, 2, 98, ["Asset Class"]).model_dump()
    out = CommentaryService(settings).generate(res)
    assert out["source"] == "unavailable"


# ------------------------------------------- natural-language parameter parser
def _parser(repo):
    from backend.services.parameter_parser_service import ParameterParserService
    return ParameterParserService(get_settings(), repo)


def test_nl_resolve_test1_partial(repo):
    # "Trading for 1 day using past 6 days" -> confidence/dimensions default.
    parsed = {"portfolio_type": "Trading", "risk_horizon_days": 1, "historical_pnl_lookback": 6,
              "confidence_level": None, "commentary_dimensions": None}
    r = _parser(repo).resolve(parsed, None)
    assert r["portfolio_type"] == "Trading" and r["risk_horizon_days"] == 1
    assert r["historical_pnl_lookback"] == 6            # 6 observations (not a preset), still valid
    assert r["confidence_level"] == 99                  # default
    assert len(r["commentary_dimensions"]) == 7         # all default dimensions


def test_nl_resolve_test2_full(repo):
    parsed = {"portfolio_type": "Trading", "risk_horizon_days": 2, "historical_pnl_lookback": 5,
              "confidence_level": 98, "commentary_dimensions": None}
    r = _parser(repo).resolve(parsed, None)
    assert (r["portfolio_type"], r["risk_horizon_days"], r["historical_pnl_lookback"], r["confidence_level"]) == ("Trading", 2, 5, 98)
    assert len(r["commentary_dimensions"]) == 7


def test_nl_resolve_test3_dimensions(repo):
    parsed = {"portfolio_type": "Trading", "risk_horizon_days": 1, "historical_pnl_lookback": None,
              "confidence_level": 99, "commentary_dimensions": ["Asset Class", "Business", "Scenario"]}
    r = _parser(repo).resolve(parsed, None)
    assert r["historical_pnl_lookback"] == 5            # default
    assert r["commentary_dimensions"] == ["Asset Class", "Business", "Scenario"]


def test_nl_resolve_test4_all_defaults(repo):
    r = _parser(repo).resolve({"portfolio_type": None, "risk_horizon_days": None, "historical_pnl_lookback": None,
                               "confidence_level": None, "commentary_dimensions": None}, None)
    assert (r["portfolio_type"], r["risk_horizon_days"], r["historical_pnl_lookback"], r["confidence_level"]) == ("Trading", 1, 5, 99)
    assert len(r["commentary_dimensions"]) == 7
    assert r["interpretation"] == "Trading | 1-Day Horizon | 5 Historical P&L Observations | 99% Confidence | 7 Commentary Dimensions"


def test_nl_resolve_test5_accuracy(repo):
    # "Use 6 days history and 98% accuracy." -> accuracy normalised to confidence upstream.
    parsed = {"portfolio_type": None, "risk_horizon_days": None, "historical_pnl_lookback": 6,
              "confidence_level": 98, "commentary_dimensions": None}
    r = _parser(repo).resolve(parsed, None)
    assert (r["portfolio_type"], r["risk_horizon_days"], r["historical_pnl_lookback"], r["confidence_level"]) == ("Trading", 1, 6, 98)


def test_nl_resolve_rejects_invalid(repo):
    parsed = {"portfolio_type": "Banking", "risk_horizon_days": 10, "historical_pnl_lookback": 999,
              "confidence_level": 150, "commentary_dimensions": ["Nonsense", "asset class", "scenarios"]}
    r = _parser(repo).resolve(parsed, None)
    assert r["portfolio_type"] == "Trading"             # Banking not allowed -> default
    assert r["risk_horizon_days"] == 1                  # 10 not supported (only 10 dates) -> default
    assert r["historical_pnl_lookback"] == 5            # 999 out of range -> default
    assert r["confidence_level"] == 99                  # 150 out of range -> default
    assert r["commentary_dimensions"] == ["Asset Class", "Scenario"]  # unsupported dropped, synonyms normalised


def test_nl_resolve_fraction_confidence(repo):
    # Model returns 0.98 for "98%" -> normalise to 98.
    r = _parser(repo).resolve({"confidence_level": 0.98}, None)
    assert r["confidence_level"] == 98


def test_nl_resolve_all_dimensions_token(repo):
    r = _parser(repo).resolve({"commentary_dimensions": ["all"]}, None)
    assert len(r["commentary_dimensions"]) == 7


def test_nl_resolve_respects_current_override(repo):
    # Sentence omits confidence; current dropdown says 95 -> keep 95 (manual override respected).
    current = {"portfolio_type": "Trading", "forward_horizon_days": 1, "lookback_days": 3,
               "confidence_level": 95, "dimensions": ["Desk", "Book"]}
    r = _parser(repo).resolve({"historical_pnl_lookback": 6}, current)
    assert r["confidence_level"] == 95 and r["historical_pnl_lookback"] == 6
    assert r["commentary_dimensions"] == ["Desk", "Book"]


# ------------------------------------------------------------- save simulation
def test_save_simulation_persists_calculated_var(repo, tmp_path):
    from backend.services.output_service import OutputService
    import pandas as pd

    out_path = tmp_path / "Market_Risk_Simulation_Output.xlsx"
    svc = OutputService(out_path)

    res = SimulationOrchestrator(repo).run("Trading", 1, 5, 99, []).model_dump()
    calc_var = res["simulation"]["simulation_var"]

    saved = svc.save_simulation(res)
    assert saved["saved"] is True and out_path.exists()
    assert saved["runs_in_file"] == 1

    runs = pd.read_excel(out_path, "simulation_runs")
    assert runs.iloc[0]["simulationVar"] == calc_var
    # The stored -$38m is never written.
    assert abs(runs.iloc[0]["simulationVar"] - 38000000) > 1

    # A second save appends (no overwrite).
    svc.save_simulation(SimulationOrchestrator(repo).run("Trading", 1, 3, 99, []).model_dump())
    runs2 = pd.read_excel(out_path, "simulation_runs")
    assert len(runs2) == 2
    pnl = pd.read_excel(out_path, "pnl_distribution")
    assert set(pnl["runId"]).issubset(set(runs2["runId"]))
