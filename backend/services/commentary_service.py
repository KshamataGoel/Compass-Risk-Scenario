"""Management commentary generation — the ONLY place Groq is used.

Groq never receives the raw workbook and never calculates anything. It receives a
compact, controlled JSON of already-derived facts and is instructed to summarise
only those facts, respecting the user's selected dimensions.
"""
from __future__ import annotations

import datetime as _dt
import json
from typing import Any

import httpx

from backend.config import Settings

SYSTEM_PROMPT = """You are a senior Market Risk commentary writer. You receive a JSON object of
already-calculated facts (a `management_brief_inputs` block plus supporting audit blocks) and
write ONE concise senior-management commentary paragraph that provides INSIGHT — not a
dashboard walkthrough.

You are a LANGUAGE LAYER ONLY. You must NOT: calculate VaR, calculate percentages or
contributions, choose the main driver, decide the VaR trend, infer causal relationships,
invent explanations, convert exposure into contribution, treat stress P&L as VaR, or treat
stored business-unit / sensitivity reference metrics as current VaR contribution. Every
number, direction, driver and classification must come from the supplied evidence.

OUTPUT FORMAT (hard limits):
- ONE paragraph, approximately 70-110 words, AT MOST 4 sentences. Plain prose only.
- No bullet points, no headings, no markdown, no dashboard walkthrough.
- Do NOT enumerate business units, desks, books, instruments, risk factors, sensitivities,
  positions, or every asset class / every contribution percentage.
- Use the display strings in `management_brief_inputs` VERBATIM for money and percentages;
  never rescale magnitudes (values are in millions/thousands, not billions).

WRITE THESE SENTENCES IN ORDER, in natural management language:
1. VaR position & trend. Template: "[risk_horizon] [portfolio_type] VaR
   [decreased/increased/remained broadly steady] to [current_var] from [previous_var], a
   [variance_pct_abs] [reduction/increase], with utilisation at [utilisation] of the Warning
   Trigger." Pick the verb from `var_trend`; if it is Steady, say "remained broadly steady"
   and drop the "a X% reduction/increase" clause. If previous_var is unavailable, state the
   current VaR and utilisation only.
   MULTI-DAY TREND: if `var_trend_phrase` is present, append it naturally (e.g. "..., a 66.7%
   reduction, continuing the recent downward trend, with utilisation..."). Do NOT invent or
   infer a broader trend when `var_trend_phrase` is null (that means the recent series does
   not confirm the current move — state only the current movement). You MAY mention at most
   ONE earlier value, `earlier_var_reference` (e.g. "down from a recent peak of $631.7k"),
   and only when it materially clarifies the direction; never quote the whole series.
2. Main VaR-tail driver. Template: "The selected VaR-tail loss was primarily driven by
   [main_tail_driver] exposure, contributing [main_tail_amount] ([main_tail_share] of the tail
   loss)" then, only if present, ", with smaller losses from [secondary_loss_contributors
   joined naturally]" and ", partly offset by [offsets]". Say "selected VaR-tail loss", NEVER
   "most recent observation". Do not repeat every contribution percentage.
3. Scenario context — ONLY if `scenario_context` is present. Begin with "Separately," or "The
   portfolio also remains exposed to" and state the scenario name and its recorded stress
   loss. NEVER imply the stress loss caused the VaR — VaR and stress P&L are separate measures.
4. Optional 4th sentence ONLY if `material_dimension_note` is present and adds something not
   already covered; otherwise stop at sentence 3.

If a fact needed for a sentence is missing, omit that sentence rather than guessing. Return
only the paragraph text."""


class CommentaryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_evidence(self, simulation_result: dict[str, Any]) -> dict[str, Any]:
        """Reduce the full simulation result to the focused, materiality-ordered fact set the
        concise management summary is written from. All figures are already calculated by the
        deterministic Python layer; nothing here is computed by the LLM."""
        sr = simulation_result
        unit_ccy = ((sr.get("simulation", {}) or {}).get("unit")) or "USD"
        selected = sr.get("selected_commentary_dimensions", [])
        sim = sr.get("simulation", {}) or {}
        tail = sr.get("tail_contribution", {}) or {}
        util = (sr.get("thresholds", {}) or {}).get("utilisation", {}) or {}

        # --- Raw calculated blocks (kept for audit/traceability in the evidence panel).
        simulation_var = {
            "available": sim.get("available", False),
            "methodology": sim.get("methodology"),
            "current_var": sim.get("simulation_var"),
            "previous_var": sim.get("previous_simulation_var"),
            "previous_available": sim.get("previous_available"),
            "var_variance": sim.get("var_variance"),
            "var_variance_pct": sim.get("var_variance_pct"),
            "var_trend": sim.get("var_trend_classification"),
            "confidence_level": sim.get("confidence_level"),
            "horizon_days": sim.get("horizon_days"),
            "lookback_days": sim.get("lookback_days"),
            "unit": sim.get("unit"),
        }
        tail_evidence = None
        secondary_names: list[str] = []
        offset_names: list[str] = []
        if tail.get("available"):
            by_exposure = tail.get("by_exposure", []) or []
            losses = sorted([r for r in by_exposure if (r.get("tail_pnl") or 0) < 0], key=lambda r: r.get("tail_pnl"))
            main_name = tail.get("main_tail_loss_driver")
            secondary_names = [r.get("exposure") for r in losses if r.get("exposure") != main_name]
            offset_names = [r.get("exposure") for r in by_exposure if (r.get("tail_pnl") or 0) > 0]
            tail_evidence = {
                "tail_period": {"start_date": tail.get("tail_start_date"), "end_date": tail.get("tail_end_date"),
                                "tail_pnl": tail.get("net_tail_pnl")},
                "tail_loss_contribution": [
                    {"exposure": r.get("exposure"), "pnl": r.get("tail_pnl"), "share_pct": r.get("share_pct"),
                     "classification": r.get("classification")} for r in by_exposure
                ],
                "asset_class_tail_contribution": [
                    {"asset_class": r.get("exposure"), "pnl": r.get("tail_pnl"), "share_pct": r.get("share_pct")}
                    for r in (tail.get("by_asset_class", []) or [])
                ],
                "main_tail_loss_driver": tail.get("main_tail_loss_driver"),
                "main_tail_loss_amount": tail.get("main_tail_loss_amount"),
                "main_tail_loss_share_pct": tail.get("main_tail_loss_share_pct"),
            }

        # --- Scenario context: ONLY when the user selected the Scenario dimension.
        scenario_context = None
        if "Scenario" in selected:
            stress = sr.get("stress_pnl", {}) or {}
            if stress.get("available"):
                scenario_context = {
                    "scenario_name": _scenario_name(sr),
                    "stress_loss": _short_money(stress.get("total_pnl"), unit_ccy),
                    "stress_loss_raw": stress.get("total_pnl"),
                }

        # --- Deterministic multi-day trend pattern from the calculated VaR series
        # (Python decides the pattern; the LLM only phrases it).
        pat = _trend_pattern(sim.get("var_trend", []) or [], sim.get("var_trend_classification"))

        # --- Focused inputs the four sentences are written from (all pre-formatted).
        prev_avail = bool(sim.get("previous_available"))
        var_pct = sim.get("var_variance_pct")
        brief = {
            "risk_horizon": _horizon_label(sim.get("horizon_days")),
            "portfolio_type": (sr.get("simulation_parameters", {}) or {}).get("portfolio_type"),
            "var_trend": sim.get("var_trend_classification"),           # Increased / Steady / Decreased
            "current_var": _short_money(sim.get("simulation_var"), unit_ccy),
            "previous_var": _short_money(sim.get("previous_simulation_var"), unit_ccy) if prev_avail else None,
            "previous_var_available": prev_avail,
            "variance_pct_abs": (f"{abs(var_pct):.1f}%" if var_pct is not None else None),
            # Multi-day trend context from the calculated VaR series (Python-classified).
            "var_trend_pattern": pat["pattern"],           # continuing_downward / continuing_upward / broadly_steady / current_only
            "var_trend_phrase": pat["phrase"],             # e.g. "continuing the recent downward trend" (or null)
            "earlier_var_reference": (
                {"as_of_date": pat["earlier"]["as_of_date"], "value": _short_money(pat["earlier"]["simulation_var"], unit_ccy)}
                if pat["earlier"] else None
            ),
            "utilisation": (f"{util.get('utilisation_pct')}%" if util.get("available") else None),
            "main_tail_driver": tail.get("main_tail_loss_driver") if tail.get("available") else None,
            "main_tail_amount": _short_money(abs(tail.get("main_tail_loss_amount")) if tail.get("main_tail_loss_amount") is not None else None, unit_ccy),
            "main_tail_share": (f"{tail.get('main_tail_loss_share_pct')}%" if tail.get("main_tail_loss_share_pct") is not None else None),
            "secondary_loss_contributors": secondary_names,
            "offsets": offset_names,
            "scenario_context": scenario_context,
            "material_dimension_note": None,   # reserved; only set when a selected dimension is genuinely material
        }

        return {
            "management_brief_inputs": brief,
            "simulation_parameters": {
                "portfolio_type": brief["portfolio_type"],
                "risk_horizon": brief["risk_horizon"],
                "confidence_level": sim.get("confidence_level"),
                "lookback_observations": sim.get("lookback_days"),
                "as_of_date": (sr.get("simulation_parameters", {}) or {}).get("as_of_date"),
            },
            # Supporting audit blocks (do not enumerate) — prove every brief figure is calculated.
            "simulation_var": simulation_var,
            "var_utilisation": util,
            "tail_contribution": tail_evidence,
            "scenario_context": scenario_context,
            "selected_commentary_dimensions": selected,
        }

    def generate(self, simulation_result: dict[str, Any]) -> dict[str, Any]:
        evidence = self.build_evidence(simulation_result)
        selected = simulation_result.get("selected_commentary_dimensions", [])

        if not self.settings.groq_configured:
            return {
                "commentary": (
                    "Management commentary generation is unavailable: GROQ_API_KEY is not configured. "
                    "All deterministic facts are shown above and in the evidence panel; only the natural-language "
                    "summary requires the LLM."
                ),
                "generated_at": _now(),
                "model": self.settings.groq_model,
                "evidence": evidence,
                "selected_dimensions": selected,
                "source": "unavailable",
            }

        user_content = json.dumps(evidence, default=str, ensure_ascii=False)
        payload = {
            "model": self.settings.groq_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    "Write the concise management commentary from these calculated facts. Base the "
                    "sentences on `management_brief_inputs`; the other blocks are supporting audit "
                    "detail and must not be enumerated.\n" + user_content
                )},
            ],
        }
        headers = {"Authorization": f"Bearer {self.settings.groq_api_key}", "Content-Type": "application/json"}
        url = f"{self.settings.groq_base_url}/chat/completions"

        # TLS verification: a corporate CA bundle path, or a bool. Lets the app work
        # behind an SSL-intercepting proxy without weakening anything by default.
        verify: Any = self.settings.groq_ca_bundle or self.settings.groq_verify_ssl
        try:
            with httpx.Client(timeout=60.0, verify=verify) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                commentary = data["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001 - surface a clean message, never fabricate commentary
            return {
                "commentary": f"Commentary could not be generated (Groq request failed: {exc}). The deterministic facts remain available in the evidence panel.",
                "generated_at": _now(),
                "model": self.settings.groq_model,
                "evidence": evidence,
                "selected_dimensions": selected,
                "source": "error",
            }

        return {
            "commentary": commentary,
            "generated_at": _now(),
            "model": self.settings.groq_model,
            "evidence": evidence,
            "selected_dimensions": selected,
            "source": "groq",
        }


def _short_money(v: Any, ccy: str = "USD") -> str | None:
    """Compact management-style money string, e.g. '$157.9k', '$11.1m'."""
    if v is None:
        return None
    symbol = "$" if ccy == "USD" else ""
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1_000_000_000:
        body = f"{a/1_000_000_000:.1f}bn"
    elif a >= 1_000_000:
        body = f"{a/1_000_000:.1f}m"
    elif a >= 1_000:
        body = f"{a/1_000:.1f}k"
    else:
        body = f"{a:,.0f}"
    return f"{sign}{symbol}{body}"


def _trend_pattern(trend_points: list[dict[str, Any]], current_class: str | None) -> dict[str, Any]:
    """Classify the recent multi-day VaR series direction, deterministically.

    Only claims a broader trend when the current-vs-previous move AGREES with the
    recent series (majority of period steps). If they conflict, returns 'current_only'
    so the commentary states only the current movement. The LLM never decides this.
    """
    pts = [p for p in trend_points if p.get("simulation_var") is not None]
    none = {"pattern": None, "phrase": None, "earlier": None}
    if len(pts) < 3 or not current_class:
        return none

    ups = sum(1 for p in pts if p.get("trend") == "Increased")
    downs = sum(1 for p in pts if p.get("trend") == "Decreased")
    vals = [p["simulation_var"] for p in pts]
    current_val = vals[-1]

    if current_class == "Decreased" and downs > ups:
        peak_i = max(range(len(vals)), key=lambda i: vals[i])
        earlier = pts[peak_i] if vals[peak_i] > current_val else None
        return {"pattern": "continuing_downward", "phrase": "continuing the recent downward trend", "earlier": earlier}
    if current_class == "Increased" and ups > downs:
        trough_i = min(range(len(vals)), key=lambda i: vals[i])
        earlier = pts[trough_i] if vals[trough_i] < current_val else None
        return {"pattern": "continuing_upward", "phrase": "continuing the recent upward trend", "earlier": earlier}
    if current_class == "Steady" and ups == 0 and downs == 0:
        # The verb "remained broadly steady" already conveys this; no extra phrase.
        return {"pattern": "broadly_steady", "phrase": None, "earlier": None}
    # Current move conflicts with, or is not confirmed by, the broader series.
    return {"pattern": "current_only", "phrase": None, "earlier": None}


def _horizon_label(horizon_days: Any) -> str | None:
    if horizon_days is None:
        return None
    try:
        n = int(horizon_days)
    except (TypeError, ValueError):
        return None
    return f"{n}-day"


def _scenario_name(sr: dict[str, Any]) -> str | None:
    """Name of the scenario that carries the recorded stress P&L (the one shown to management)."""
    for s in ((sr.get("scenario_analysis", {}) or {}).get("scenarios", []) or []):
        if (s.get("scenario_pnl", {}) or {}).get("available"):
            return s.get("scenarioSetName")
    return None


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()
