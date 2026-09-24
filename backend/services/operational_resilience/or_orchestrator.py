"""Operational Resilience orchestrator.

Composes the deterministic impact services into one governed result with lineage, plus a
compact evidence object for the commentary layer. Detects requests for dimensions the LDM
does not represent and marks them UNAVAILABLE instead of inventing an answer.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from backend.data.excel_repository import ExcelRepository
from backend.services.operational_resilience.impact_service import (
    SUPPORTED_DIMENSIONS,
    UNAVAILABLE_MSG,
    ImpactService,
)
from backend.services.operational_resilience.scenario_service import ScenarioService

# Phrases that map to concepts absent from the LDM (README-confirmed).
_UNSUPPORTED_PATTERNS = {
    "industry / sector": r"\b(industry|sector|semiconductor|automobile|automotive)\b",
    "vendor / third-party inventory": r"\b(vendor|supplier|suppliers|third[- ]party (name|inventory|list))\b",
    "people / headcount": r"\b(employee|employees|headcount|people|staff) (count|impacted|affected)\b|\bhow many (people|employees|staff)\b",
    "physical-site inventory": r"\b(site inventory|physical site|number of sites|which sites)\b",
}


class OROrchestrator:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo
        self.scenario_service = ScenarioService(repo)
        self.impact = ImpactService(repo)

    def run(self, text: str, scenario_id: str | None = None, requested_dimensions: list[str] | None = None) -> dict[str, Any]:
        resolution = self.scenario_service.resolve(text, explicit_id=scenario_id)
        if not resolution.get("available"):
            return {
                "risk_stripe": "OPERATIONAL_RESILIENCE",
                "available": False,
                "message": resolution.get("reason"),
                "candidates": resolution.get("candidates", []),
                "generated_at": _now(),
            }

        sid = resolution["scenario_id"]
        scenario = resolution["scenario"]
        event_ids = self.scenario_service.scenario_event_ids(sid)
        events = self.impact._events(event_ids)
        risk_ids = self.impact._risk_ids(events)

        dims = requested_dimensions or SUPPORTED_DIMENSIONS
        unavailable = self._detect_unavailable(text)

        event_impact = self.impact.event_impact(events)
        locations = self.impact.locations(events)
        risks = self.impact.risks(risk_ids)
        business_services = self.impact.business_services(risk_ids)
        business_processes = self.impact.business_processes(risk_ids)
        business_units = self.impact.business_units(risk_ids)
        legal_entities = self.impact.legal_entities(events)
        threshold_breaches = self.impact.threshold_breaches(risk_ids)
        controls = self.impact.controls(risk_ids)
        issues = self.impact.issues(events, risk_ids)
        issue_ids = [i["issueId"] for i in issues.get("issues", [])]
        actions = self.impact.actions(issue_ids)

        result = {
            "risk_stripe": "OPERATIONAL_RESILIENCE",
            "available": True,
            "generated_at": _now(),
            "scenario_resolution": {k: resolution[k] for k in ("scenario_id", "match_method", "match_score")},
            "scenario": scenario,
            "requested_dimensions": dims,
            "supported_dimensions": SUPPORTED_DIMENSIONS,
            "event_impact": event_impact,
            "locations": locations,
            "risks": risks,
            "business_services": business_services,
            "business_processes": business_processes,
            "business_units": business_units,
            "legal_entities": legal_entities,
            "threshold_breaches": threshold_breaches,
            "controls": controls,
            "issues": issues,
            "actions": actions,
            "unavailable": unavailable,
            "lineage": self._lineage(),
        }
        result["evidence"] = self._evidence(result)
        return result

    # ------------------------------------------------------------- helpers
    def _detect_unavailable(self, text: str) -> list[dict[str, str]]:
        t = (text or "").lower()
        out = []
        for label, pattern in _UNSUPPORTED_PATTERNS.items():
            if re.search(pattern, t):
                out.append({"dimension": label, "status": "UNAVAILABLE", "reason": UNAVAILABLE_MSG})
        return out

    def _lineage(self) -> dict[str, Any]:
        return {
            "Scenario Name": {"status": "INPUT", "source": "scenario.scenarioName"},
            "Related Events": {"status": "CALCULATED", "source": "risk_event within scenario anchor range (scenario.eventIdentifier)"},
            "Event Duration": {"status": "CALCULATED", "source": "MAX(risk_event.eventDateTimeEnd) - MIN(risk_event.eventDateTimeStart)"},
            "Total Financial Impact": {"status": "CALCULATED", "source": "SUM(risk_event.financialImpactAmount)"},
            "Impacted Locations": {"status": "CALCULATED", "source": "COUNT DISTINCT risk_event.locationId -> region_country"},
            "Risk Impact Rating": {"status": "INPUT", "source": "risk.impactRating"},
            "Risk Type": {"status": "INPUT", "source": "risk.riskTypeId -> risk_type.riskType"},
            "Business Services": {"status": "CALCULATED", "source": "risk.businessServiceId -> business_service"},
            "Business Processes": {"status": "CALCULATED", "source": "risk.businessProcessId -> business_process"},
            "Business Units": {"status": "CALCULATED", "source": "risk.businessUnitId -> hsbc_global_Business_Unit"},
            "Legal Entities": {"status": "CALCULATED", "source": "location -> hsbc_legal_entity_GBU_location -> hsbc_legal_entity"},
            "Threshold Breaches": {"status": "CALCULATED", "source": "risk_metric_obs -> risk_threshold_breach"},
            "Breach Severity": {"status": "INPUT", "source": "risk_threshold_breach.breachSeverity"},
            "Controls": {"status": "INPUT", "source": "control (control.riskIdentifier); rating from risk_assessment.controlRating"},
            "Issues": {"status": "INPUT", "source": "issue (risk_event.issueId / issue.riskIdentifier)"},
            "Actions": {"status": "INPUT", "source": "action (action.issueId)"},
            "Management Summary": {"status": "LLM", "source": "Groq, from CALCULATED/INPUT evidence only"},
        }

    def _evidence(self, r: dict[str, Any]) -> dict[str, Any]:
        ei = r["event_impact"]
        tb = r["threshold_breaches"]
        return {
            "risk_stripe": "OPERATIONAL_RESILIENCE",
            "scenario": {"name": r["scenario"].get("scenarioName"), "impact": r["scenario"].get("scenarioImpact")},
            "event_impact": {
                "event_count": ei.get("event_count"),
                "period_start": ei.get("period_start"),
                "period_end": ei.get("period_end"),
                "duration_hours": ei.get("duration_hours"),
                "total_financial_impact": ei.get("total_financial_impact"),
                "currency": ei.get("currency"),
                "likelihood_breakdown": ei.get("likelihood_breakdown"),
            },
            "location_count": len(r["locations"]),
            "locations": [l["locationName"] for l in r["locations"] if l.get("locationName")],
            "risk_count": len(r["risks"]),
            "risk_impact_ratings": _tally([x.get("impactRating") for x in r["risks"]]),
            "risk_types": sorted({x.get("riskType") for x in r["risks"] if x.get("riskType")}),
            "business_service_count": len(r["business_services"]),
            "business_services": [s["serviceName"] for s in r["business_services"] if s.get("serviceName")],
            "business_process_count": len(r["business_processes"]),
            "business_unit_count": len(r["business_units"]),
            "legal_entity_count": len(r["legal_entities"]),
            "threshold_breaches": {
                "breach_count": tb.get("breach_count") if tb.get("available") else 0,
                "open_breach_count": tb.get("open_breach_count") if tb.get("available") else 0,
                "severity_breakdown": tb.get("severity_breakdown") if tb.get("available") else {},
            },
            "issues": {"total": r["issues"].get("total", 0), "open": r["issues"].get("open", 0)},
            "actions": {"total": r["actions"].get("total", 0), "open": r["actions"].get("open", 0)},
            "unavailable": r["unavailable"],
        }


def _tally(values: list[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        if v is None:
            continue
        out[str(v)] = out.get(str(v), 0) + 1
    return out


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()
