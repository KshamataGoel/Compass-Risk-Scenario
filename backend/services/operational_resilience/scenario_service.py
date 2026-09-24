"""Operational Resilience scenario resolution + event grouping.

Resolves a natural-language phrase to one of the workbook's scenarios by semantic/name
matching against the actual scenario data (name, description, impact), and partitions
risk_event rows to scenarios using each scenario's anchor event (scenario.eventIdentifier):
a scenario owns the contiguous run of events from its anchor up to the next scenario's
anchor. No relationship is invented — the anchors come from the workbook.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from backend.data.excel_repository import ExcelRepository

# Stop words: articles + verbs + the DIMENSION words (service/location/etc.) that appear in
# scenario impact text and must not drive scenario resolution — only discriminating words do.
_STOP = {"the", "a", "an", "of", "for", "on", "to", "and", "impact", "impacts", "impacted",
         "affected", "show", "run", "assess", "scenario", "scenarios", "operational",
         "resilience", "our", "from", "me", "tell", "with", "what", "which", "please", "risk",
         "risks", "disruption", "disruptions", "service", "services", "location", "locations",
         "process", "processes", "business", "event", "events", "issue", "issues", "action",
         "actions", "control", "controls", "breach", "breaches", "open", "closed", "unit",
         "units", "entity", "entities", "critical", "system", "give", "get"}

# Scenario-type synonym anchors (per the brief §4) — each maps a phrase to distinguishing
# tokens. These reinforce, and are cross-checked against, the workbook scenario names.
_SYNONYMS = {
    "storm": "storm", "weather": "storm", "severe": "storm", "asian": "storm", "flood": "storm",
    "typhoon": "storm", "cyclone": "storm",
    "technology": "technology", "tech": "technology", "outage": "technology", "system": "technology",
    "systems": "technology", "it": "technology", "cyber": "technology", "software": "technology",
    "third": "supply", "party": "supply", "supply": "supply", "chain": "supply", "vendor": "supply",
    "supplier": "supply", "suppliers": "supply", "external": "supply", "dependency": "supply",
}
# Which anchor group each scenario belongs to, discovered from its own name text.
_ANCHOR_KEYS = {"storm": ("storm", "weather", "severe"), "technology": ("technology", "system", "critical"),
                "supply": ("third", "party", "supply", "chain")}


class ScenarioService:
    def __init__(self, repo: ExcelRepository) -> None:
        self.repo = repo

    def all_scenarios(self) -> list[dict[str, Any]]:
        scen = self.repo.get("scenario")
        scen = scen.sort_values("eventIdentifier")
        return scen.where(pd.notna(scen), None).to_dict("records")

    # ---------------------------------------------------- scenario resolution
    def resolve(self, text: str, explicit_id: str | None = None) -> dict[str, Any]:
        scen = self.repo.get("scenario")
        ids = set(scen["scenarioIdentifier"])

        # 1) Explicit id (e.g. "SCN002") wins.
        if explicit_id and explicit_id in ids:
            return self._matched(explicit_id, "explicit_id", 1.0)
        m = re.search(r"\bSCN\d{3}\b", (text or "").upper())
        if m and m.group(0) in ids:
            return self._matched(m.group(0), "explicit_id", 1.0)

        # 2) Match on the discriminating scenario NAME/DESCRIPTION tokens plus scenario-type
        #    synonym anchors (name text drives resolution, not the generic impact/dimension text).
        user_tokens = _tokens(text)
        user_anchor = {_SYNONYMS[w] for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w in _SYNONYMS}
        best_id, best_score = None, 0.0
        for _, row in scen.iterrows():
            name_desc = " ".join(str(row.get(c, "")) for c in ("scenarioName", "scenarioDescription"))
            ctoks = _tokens(name_desc)
            scen_anchor = {_SYNONYMS[w] for w in re.findall(r"[a-z0-9]+", name_desc.lower()) if w in _SYNONYMS}
            overlap = len(user_tokens & ctoks)
            anchor_hit = len(user_anchor & scen_anchor)
            score = overlap + 2.0 * anchor_hit  # anchor agreement weighted highest
            if score > best_score:
                best_id, best_score = row["scenarioIdentifier"], score

        if best_id is not None and best_score > 0:
            return self._matched(best_id, "semantic_name_match", round(float(best_score), 2))

        # 3) No match — expose the available scenarios so the UI can prompt, without guessing.
        return {
            "available": False,
            "reason": "Could not resolve a scenario from the request.",
            "candidates": [
                {"scenario_id": r["scenarioIdentifier"], "name": r.get("scenarioName")}
                for _, r in scen.sort_values("scenarioIdentifier").iterrows()
            ],
        }

    def _matched(self, scenario_id: str, method: str, score: float) -> dict[str, Any]:
        scen = self.repo.get("scenario")
        row = scen[scen["scenarioIdentifier"] == scenario_id].iloc[0]
        return {
            "available": True,
            "scenario_id": scenario_id,
            "match_method": method,
            "match_score": score,
            "scenario": {
                "scenarioIdentifier": scenario_id,
                "scenarioName": row.get("scenarioName"),
                "scenarioDescription": row.get("scenarioDescription"),
                "scenarioImpact": row.get("scenarioImpact"),
                "impactBreakdown": row.get("impactBreakdown"),
                "anchor_event": row.get("eventIdentifier"),
                "owner": row.get("owner"),
            },
        }

    # ------------------------------------------------------- event grouping
    def scenario_event_ids(self, scenario_id: str) -> list[str]:
        """Events owned by a scenario: from its anchor up to the next scenario's anchor
        (contiguous run over ordered eventIdentifier). Derived only from workbook anchors."""
        scen = self.repo.get("scenario").sort_values("eventIdentifier")
        anchors = list(scen[["scenarioIdentifier", "eventIdentifier"]].itertuples(index=False, name=None))
        events = self.repo.get("risk_event")
        all_event_ids = sorted(events["eventIdentifier"].dropna().unique().tolist())

        # Ordered anchor list -> [start_anchor, next_anchor) ranges.
        this_anchor = next((ev for sid, ev in anchors if sid == scenario_id), None)
        if this_anchor is None:
            return []
        anchor_positions = [ev for _, ev in anchors]
        start_idx = all_event_ids.index(this_anchor) if this_anchor in all_event_ids else 0
        # Find the next anchor strictly after this one.
        later_anchors = [a for a in anchor_positions if a in all_event_ids and all_event_ids.index(a) > start_idx]
        end_idx = min((all_event_ids.index(a) for a in later_anchors), default=len(all_event_ids))
        return all_event_ids[start_idx:end_idx]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in _STOP}
