"""Operational Resilience deterministic impact calculations.

Every figure is computed in Python from the OR workbook. The LLM never calculates any
of these. Requested dimensions that the model cannot support are returned as UNAVAILABLE
rather than invented.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository

UNAVAILABLE_MSG = "Not represented in the current Operational Resilience data model."

# Dimensions the model can support (used for defaults and to flag unsupported requests).
SUPPORTED_DIMENSIONS = [
    "location", "business_service", "business_process", "risk", "risk_type",
    "business_unit", "legal_entity", "threshold_breach", "control", "issue", "action",
]
# Things management may ask about that this LDM does not represent.
UNSUPPORTED_DIMENSIONS = {
    "industry", "sector", "vendor", "supplier", "third_party_inventory", "people",
    "employee", "headcount", "site", "physical_site", "semiconductor", "automobile",
}


class ImpactService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def _events(self, event_ids: list[str]) -> pd.DataFrame:
        ev = self.repo.get("risk_event")
        return ev[ev["eventIdentifier"].isin(event_ids)].copy()

    def _risk_ids(self, events: pd.DataFrame) -> list[str]:
        return sorted(events["riskIdentifier"].dropna().unique().tolist())

    # ---------------------------------------------------------- A. event impact
    def event_impact(self, events: pd.DataFrame) -> dict[str, Any]:
        if events.empty:
            return {"available": False, "reason": "No events for scenario."}
        start = pd.to_datetime(events["eventDateTimeStart"], errors="coerce")
        end = pd.to_datetime(events["eventDateTimeEnd"], errors="coerce")
        window_start, window_end = start.min(), end.max()
        duration_hours = None
        if pd.notna(window_start) and pd.notna(window_end):
            duration_hours = round((window_end - window_start).total_seconds() / 3600.0, 1)
        fin = pd.to_numeric(events.get("financialImpactAmount"), errors="coerce")
        return {
            "available": True,
            "event_count": int(len(events)),
            "period_start": str(window_start) if pd.notna(window_start) else None,
            "period_end": str(window_end) if pd.notna(window_end) else None,
            "duration_hours": duration_hours,
            "total_financial_impact": float(fin.sum()) if fin.notna().any() else None,
            "currency": _first(events.get("financialImpactCurrency")),
            "likelihood_breakdown": _counts(events, "likelihood"),
            "event_statuses": _counts(events, "eventStatusCode"),
            "non_financial_impact_types": sorted(events["nonFinancialImpactType"].dropna().unique().tolist())
            if "nonFinancialImpactType" in events.columns else [],
        }

    # ------------------------------------------------------------ B. locations
    def locations(self, events: pd.DataFrame) -> list[dict[str, Any]]:
        rc = self.repo.get("region_country")
        by_loc = events.groupby("locationId").size().to_dict()
        out = []
        for loc_id, cnt in by_loc.items():
            r = rc[rc["locationId"] == loc_id]
            row = r.iloc[0] if not r.empty else None
            out.append({
                "locationId": loc_id,
                "locationName": (row.get("locationName") if row is not None else None),
                "countryName": (row.get("countryName") if row is not None else None),
                "isoCountryCode": (row.get("isoCountryCode") if row is not None else None),
                "regionCode": (row.get("regionCode") if row is not None else None),
                "event_count": int(cnt),
            })
        return sorted(out, key=lambda x: -x["event_count"])

    # --------------------------------------------------------------- C. risks
    def risks(self, risk_ids: list[str]) -> list[dict[str, Any]]:
        risk = self.repo.get("risk")
        rt = self.repo.get("risk_type", required=False)
        rt_map = {}
        if rt is not None:
            rt_map = {r["riskTypeId"]: r for _, r in rt.iterrows()}
        out = []
        for rid in risk_ids:
            r = risk[risk["riskIdentifier"] == rid]
            if r.empty:
                continue
            row = r.iloc[0]
            rtype = rt_map.get(row.get("riskTypeId"))
            out.append({
                "riskIdentifier": rid,
                "riskStatement": row.get("riskStatement"),
                "impactRating": row.get("impactRating"),
                "riskType": (rtype.get("riskType") if rtype is not None else None),
                "riskClassification": (rtype.get("riskClassification") if rtype is not None else None),
            })
        return out

    # --------------------------------------------- D/E. services & processes
    def business_services(self, risk_ids: list[str]) -> list[dict[str, Any]]:
        risk = self.repo.get("risk")
        svc = self.repo.get("business_service")
        svc_ids = sorted(risk[risk["riskIdentifier"].isin(risk_ids)]["businessServiceId"].dropna().unique().tolist())
        out = []
        for sid in svc_ids:
            s = svc[svc["businessServiceId"] == sid]
            row = s.iloc[0] if not s.empty else None
            out.append({
                "businessServiceId": sid,
                "serviceName": (row.get("serviceName") if row is not None else None),
                "serviceTier": (row.get("serviceTier") if row is not None else None),
                "serviceHours": (row.get("serviceHours") if row is not None else None),
            })
        return out

    def business_processes(self, risk_ids: list[str]) -> list[dict[str, Any]]:
        risk = self.repo.get("risk")
        bp = self.repo.get("business_process")
        bp_ids = sorted(risk[risk["riskIdentifier"].isin(risk_ids)]["businessProcessId"].dropna().unique().tolist())
        out = []
        for pid in bp_ids:
            p = bp[bp["businessProcessId"] == pid]
            row = p.iloc[0] if not p.empty else None
            out.append({"businessProcessId": pid, "businessProcessName": (row.get("businessProcessName") if row is not None else None)})
        return out

    # ------------------------------------------ F. business units & legal entities
    def business_units(self, risk_ids: list[str]) -> list[dict[str, Any]]:
        risk = self.repo.get("risk")
        gbu = self.repo.get("hsbc_global_Business_Unit")
        name_map = dict(zip(gbu["businessUnitId"], gbu["hsbcGlobalBusinessFrameworkUnitName"]))
        bu_ids = sorted(risk[risk["riskIdentifier"].isin(risk_ids)]["businessUnitId"].dropna().unique().tolist())
        return [{"businessUnitId": b, "businessUnitName": name_map.get(b)} for b in bu_ids]

    def legal_entities(self, events: pd.DataFrame) -> list[dict[str, Any]]:
        loc_ids = sorted(events["locationId"].dropna().unique().tolist())
        link = self.repo.get("hsbc_legal_entity_GBU_location", required=False)
        le = self.repo.get("hsbc_legal_entity", required=False)
        if link is None or le is None:
            return []
        le_map = {r["hsbcLegalEntityPartyId"]: r for _, r in le.iterrows()}
        seen, out = set(), []
        for loc in loc_ids:
            for _, lk in link[link["locationId"] == loc].iterrows():
                pid = lk.get("hsbcLegalEntityPartyId")
                if pid in seen:
                    continue
                seen.add(pid)
                e = le_map.get(pid)
                out.append({
                    "hsbcLegalEntityPartyId": pid,
                    "hsbcLegalEntityCode": (e.get("hsbcLegalEntityCode") if e is not None else None),
                    "locationId": loc,
                })
        return out

    # ------------------------------------------------- G. thresholds & breaches
    def threshold_breaches(self, risk_ids: list[str]) -> dict[str, Any]:
        obs = self.repo.get("risk_metric_obs", required=False)
        breach = self.repo.get("risk_threshold_breach", required=False)
        thr = self.repo.get("risk_threshold", required=False)
        if obs is None or breach is None:
            return {"available": False, "reason": UNAVAILABLE_MSG}
        obs_ids = obs[obs["riskIdentifier"].isin(risk_ids)]["riskMetricObsId"].tolist()
        obs_risk = dict(zip(obs["riskMetricObsId"], obs["riskIdentifier"]))
        b = breach[breach["riskMetricObsId"].isin(obs_ids)].copy()
        breaches = [{
            "breachId": r.get("breachId"),
            "riskIdentifier": obs_risk.get(r.get("riskMetricObsId")),
            "observedValue": _num(r.get("observedValue")),
            "breachSeverity": r.get("breachSeverity"),
            "breachStatusCode": r.get("breachStatusCode"),
            "breachDateTime": str(r.get("breachDateTime")),
        } for _, r in b.iterrows()]
        # Applicable thresholds for these risks' metrics.
        thresholds = []
        if thr is not None:
            metric_ids = obs[obs["riskIdentifier"].isin(risk_ids)]["riskMetricId"].unique().tolist()
            for _, r in thr[thr["riskMetricId"].isin(metric_ids)].iterrows():
                thresholds.append({"thresholdId": r.get("thresholdId"), "riskMetricId": r.get("riskMetricId"),
                                   "thresholdValueHigh": _num(r.get("thresholdValueHigh")), "unit": r.get("riskMetricType")})
        return {
            "available": True,
            "breach_count": len(breaches),
            "open_breach_count": sum(1 for x in breaches if x["breachStatusCode"] == "Open"),
            "severity_breakdown": _list_counts([x["breachSeverity"] for x in breaches]),
            "breaches": breaches,
            "thresholds": thresholds,
        }

    # ------------------------------------------- H. controls / issues / actions
    def controls(self, risk_ids: list[str]) -> list[dict[str, Any]]:
        control = self.repo.get("control", required=False)
        ra = self.repo.get("risk_assessment", required=False)
        if control is None:
            return []
        rating_map = {}
        if ra is not None and "controlId" in ra.columns and "controlRating" in ra.columns:
            rating_map = dict(zip(ra["controlId"], ra["controlRating"]))
        out = []
        for _, r in control[control["riskIdentifier"].isin(risk_ids)].iterrows():
            out.append({
                "controlId": r.get("controlId"),
                "controlDescription": r.get("controlDescription"),
                "controlFrequency": r.get("controlFrequency"),
                "controlRating": rating_map.get(r.get("controlId")),
                "riskIdentifier": r.get("riskIdentifier"),
            })
        return out

    def issues(self, events: pd.DataFrame, risk_ids: list[str]) -> dict[str, Any]:
        issue = self.repo.get("issue", required=False)
        if issue is None:
            return {"available": False, "reason": UNAVAILABLE_MSG}
        issue_ids = set(events["issueId"].dropna().unique().tolist())
        sub = issue[(issue["issueId"].isin(issue_ids)) | (issue["riskIdentifier"].isin(risk_ids))]
        rows = [{
            "issueId": r.get("issueId"),
            "issueDescription": r.get("issueDescription"),
            "statusCode": r.get("statusCode"),
            "severityCode": r.get("severityCode"),
            "priorityCode": r.get("priorityCode"),
            "riskIdentifier": r.get("riskIdentifier"),
        } for _, r in sub.iterrows()]
        return {
            "available": True,
            "total": len(rows),
            "open": sum(1 for r in rows if r["statusCode"] == "Open"),
            "severity_breakdown": _list_counts([r["severityCode"] for r in rows]),
            "issues": rows,
        }

    def actions(self, issue_ids: list[str]) -> dict[str, Any]:
        action = self.repo.get("action", required=False)
        if action is None:
            return {"available": False, "reason": UNAVAILABLE_MSG}
        sub = action[action["issueId"].isin(issue_ids)]
        rows = [{
            "actionId": r.get("actionId"),
            "description": r.get("description"),
            "statusCode": r.get("statusCode"),
            "targetOutcome": r.get("targetOutcome"),
            "targetDate": str(r.get("targetDate")),
            "issueId": r.get("issueId"),
        } for _, r in sub.iterrows()]
        return {
            "available": True,
            "total": len(rows),
            "open": sum(1 for r in rows if r["statusCode"] == "Open"),
            "actions": rows,
        }


def _counts(df: pd.DataFrame, col: str) -> dict[str, int]:
    if col not in df.columns:
        return {}
    return {str(k): int(v) for k, v in df[col].value_counts().to_dict().items()}


def _list_counts(values: list[Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        if v is None:
            continue
        out[str(v)] = out.get(str(v), 0) + 1
    return out


def _first(series: Any) -> Any:
    if series is None:
        return None
    s = series.dropna()
    return s.iloc[0] if not s.empty else None


def _num(v: Any) -> float | None:
    return None if v is None or pd.isna(v) else float(v)
