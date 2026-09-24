"""Risk-stripe router — classifies a natural-language request into a risk stripe.

Two stripes are supported for this POC: MARKET_RISK and OPERATIONAL_RESILIENCE.
Groq performs the classification; a deterministic keyword fallback runs when Groq is
unavailable or returns something invalid, so routing never blocks the application.

The router is extensible: add a stripe to STRIPES + the fallback lexicon and register a
new engine, without touching the existing two engines.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from backend.config import Settings

logger = logging.getLogger("risk_stripe_router")

MARKET_RISK = "MARKET_RISK"
OPERATIONAL_RESILIENCE = "OPERATIONAL_RESILIENCE"
STRIPES = (MARKET_RISK, OPERATIONAL_RESILIENCE)

ROUTER_SYSTEM_PROMPT = """You are a risk-stripe request classifier for an enterprise risk analytics application.

The application currently supports exactly two risk stripes:

MARKET_RISK:
Requests involving VaR, trading portfolio, market movements, historical simulation, interest rates, FX, market risk factors, positions, books, desks, instruments, market scenarios or market sensitivities.

OPERATIONAL_RESILIENCE:
Requests involving operational disruption, resilience scenarios, service disruption, business process disruption, technology outage, severe weather, external dependency, operational events, controls, issues, actions, threshold breaches, recovery or continuity.

Return strict JSON only.

Do not calculate metrics.
Do not invent parameters.
Do not invent entities or attributes.

If the request clearly maps to one risk stripe, classify it accordingly.

Return exactly:
{
  "risk_stripe": "MARKET_RISK | OPERATIONAL_RESILIENCE",
  "confidence": <0 to 1>,
  "reason": "<short reason>",
  "extracted_intent": "<normalized intent>"
}
No prose. No markdown."""

# Deterministic fallback lexicon (used only when Groq is unavailable / invalid).
_MARKET_TERMS = [
    "var", "value at risk", "trading", "portfolio", "market", "historical simulation",
    "interest rate", "fx", "foreign exchange", "risk factor", "position", "book", "desk",
    "instrument", "sensitivity", "confidence", "lookback", "p&l", "pnl", "horizon", "volatility",
]
_OPS_TERMS = [
    "operational", "resilience", "disruption", "outage", "storm", "weather", "technology",
    "supply chain", "supply-chain", "third party", "third-party", "vendor", "service disruption",
    "business service", "business process", "continuity", "recovery", "control", "issue",
    "action", "breach", "incident", "event", "scenario impact", "external dependency",
]


class RiskStripeRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def classify(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return self._fallback("", note="empty request")

        groq = self._classify_with_groq(text)
        if groq is not None:
            return groq
        return self._fallback(text, note="Groq unavailable; classified by keyword heuristic.")

    # ------------------------------------------------------------------ Groq
    def _classify_with_groq(self, text: str) -> dict[str, Any] | None:
        if not self.settings.groq_configured:
            return None
        payload = {
            "model": self.settings.groq_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        }
        headers = {"Authorization": f"Bearer {self.settings.groq_api_key}", "Content-Type": "application/json"}
        url = f"{self.settings.groq_base_url}/chat/completions"
        verify: Any = self.settings.groq_ca_bundle or self.settings.groq_verify_ssl
        try:
            with httpx.Client(timeout=25.0, verify=verify) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = _extract_json(resp.json()["choices"][0]["message"]["content"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Router Groq call failed: %s", exc)
            return None
        if not data:
            return None
        stripe = str(data.get("risk_stripe", "")).upper().strip()
        if stripe not in STRIPES:
            return None
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        return {
            "risk_stripe": stripe,
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": str(data.get("reason", ""))[:400],
            "extracted_intent": str(data.get("extracted_intent", ""))[:200],
            "source": "groq",
        }

    # -------------------------------------------------------------- fallback
    def _fallback(self, text: str, note: str) -> dict[str, Any]:
        t = text.lower()
        market = sum(1 for term in _MARKET_TERMS if term in t)
        ops = sum(1 for term in _OPS_TERMS if term in t)
        if ops > market:
            stripe, intent = OPERATIONAL_RESILIENCE, "Assess operational resilience scenario impact"
        elif market > ops:
            stripe, intent = MARKET_RISK, "Calculate market risk VaR"
        else:
            # Default to Market Risk (the original stripe) when ambiguous.
            stripe, intent = MARKET_RISK, "Calculate market risk VaR"
        total = market + ops
        confidence = round(max(market, ops) / total, 2) if total else 0.5
        return {
            "risk_stripe": stripe,
            "confidence": confidence,
            "reason": note if not total else f"Keyword match: {market} market vs {ops} operational term(s).",
            "extracted_intent": intent,
            "source": "fallback",
        }


def _extract_json(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except Exception:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except Exception:
                return None
    return None
