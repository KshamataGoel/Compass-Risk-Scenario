"""Operational Resilience risk-stripe tests — router, scenario resolution, deterministic
impact calculations, UNAVAILABLE handling. All values trace to the OR workbook only."""
from __future__ import annotations

import pytest

from backend.config import get_settings
from backend.services.operational_resilience.or_orchestrator import OROrchestrator
from backend.services.operational_resilience.or_repository import get_or_repository, reset_or_repository
from backend.services.operational_resilience.scenario_service import ScenarioService
from backend.services.risk_stripe_router import (
    MARKET_RISK,
    OPERATIONAL_RESILIENCE,
    RiskStripeRouter,
)


@pytest.fixture(scope="module")
def orepo():
    reset_or_repository()
    return get_or_repository()


# --------------------------------------------------------------- router
def test_router_fallback_market_vs_ops():
    r = RiskStripeRouter(get_settings())
    assert r._fallback("Trading VaR for 1 day at 99% confidence", "n")["risk_stripe"] == MARKET_RISK
    assert r._fallback("Show operational resilience impact for Asian storm", "n")["risk_stripe"] == OPERATIONAL_RESILIENCE
    assert r._fallback("Assess technology disruption and open issues", "n")["risk_stripe"] == OPERATIONAL_RESILIENCE


def test_router_classify_without_groq(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "groq_api_key", None)  # force deterministic fallback
    out = RiskStripeRouter(s).classify("Run VaR")
    assert out["risk_stripe"] == MARKET_RISK and out["source"] == "fallback"


# ------------------------------------------------------- scenario resolution
@pytest.mark.parametrize("text,expected", [
    ("Show operational resilience impact for Asian storm", "SCN001"),
    ("Assess technology disruption and tell me impacted services and open issues", "SCN002"),
    ("Show impact of third-party supply-chain disruption", "SCN003"),
    ("severe weather event", "SCN001"),
    ("system outage", "SCN002"),
    ("SCN003 please", "SCN003"),
])
def test_scenario_resolution(orepo, text, expected):
    r = ScenarioService(orepo).resolve(text)
    assert r["available"] and r["scenario_id"] == expected


def test_event_grouping_by_anchor(orepo):
    svc = ScenarioService(orepo)
    assert svc.scenario_event_ids("SCN001") == ["EVT001", "EVT002", "EVT003", "EVT004"]
    assert svc.scenario_event_ids("SCN002") == ["EVT005", "EVT006", "EVT007"]
    assert svc.scenario_event_ids("SCN003") == ["EVT008", "EVT009", "EVT010"]


# ---------------------------------------------------- deterministic impact
def test_asian_storm_impact(orepo):
    r = OROrchestrator(orepo).run("Show operational resilience impact for Asian storm")
    assert r["available"] and r["scenario_resolution"]["scenario_id"] == "SCN001"
    ei = r["event_impact"]
    assert ei["event_count"] == 4
    assert ei["total_financial_impact"] == 620000  # 250k+120k+180k+70k
    assert ei["currency"] == "USD"
    assert {l["locationName"] for l in r["locations"]} == {"Singapore", "Hong Kong", "Tokyo"}
    assert len(r["risks"]) == 2
    assert r["threshold_breaches"]["breach_count"] == 1
    # Evidence carries only calculated facts.
    assert r["evidence"]["event_impact"]["total_financial_impact"] == 620000


def test_third_party_impact(orepo):
    r = OROrchestrator(orepo).run("third-party supply-chain disruption")
    assert r["scenario_resolution"]["scenario_id"] == "SCN003"
    assert r["event_impact"]["event_count"] == 3
    assert r["event_impact"]["total_financial_impact"] == 490000  # 300k+110k+80k
    assert r["threshold_breaches"]["breach_count"] == 2


def test_unavailable_industry_vendor(orepo):
    r = OROrchestrator(orepo).run("Which semiconductor suppliers are affected by the Asian storm?")
    assert r["scenario_resolution"]["scenario_id"] == "SCN001"   # scenario still resolves
    dims = {u["dimension"] for u in r["unavailable"]}
    assert "industry / sector" in dims and "vendor / third-party inventory" in dims
    # Never invents supplier names anywhere in the payload.
    import json
    assert "semiconductor" not in json.dumps(r).lower()


def test_lineage_present(orepo):
    r = OROrchestrator(orepo).run("Asian storm")
    lin = r["lineage"]
    assert lin["Total Financial Impact"]["status"] == "CALCULATED"
    assert lin["Scenario Name"]["status"] == "INPUT"
    assert lin["Management Summary"]["status"] == "LLM"
