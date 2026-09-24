"""Operational Resilience management commentary (Groq language layer only).

Short (3-5 sentences). Groq receives ONLY the deterministic evidence and summarises it;
it never calculates, infers unsupported causality, or invents entities/metrics/dimensions.
"""
from __future__ import annotations

import datetime as _dt
import json
from typing import Any

import httpx

from backend.config import Settings

OR_COMMENTARY_SYSTEM_PROMPT = """You are an Operational Resilience management commentary writer.

You receive a JSON object of already-calculated deterministic evidence for one resilience
scenario. Write a SHORT management summary of 3-5 sentences in plain prose.

You are a language layer only. You must NOT: calculate or restate maths you were not given,
invent events, locations, services, risks, controls, issues, actions, vendors, industries,
people or sites, infer unsupported causality, or treat anything marked UNAVAILABLE as known.

Use only figures and names present in the evidence. Prioritise: scenario name, event count,
locations, financial impact, risks/impact ratings, business services/processes affected,
threshold breaches (count/severity), and open issues/actions. Mention at most what is
material. If `unavailable` is non-empty, you may note briefly that that information is not
represented in the data model. No bullet points, no headings, no markdown."""


class ORCommentaryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, or_result: dict[str, Any]) -> dict[str, Any]:
        evidence = or_result.get("evidence") or {}
        if not self.settings.groq_configured:
            return {
                "commentary": "Management commentary is unavailable: GROQ_API_KEY is not configured. All deterministic facts are shown above and in the evidence panel.",
                "generated_at": _now(), "model": self.settings.groq_model, "evidence": evidence, "source": "unavailable",
            }
        payload = {
            "model": self.settings.groq_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": OR_COMMENTARY_SYSTEM_PROMPT},
                {"role": "user", "content": "Summarise ONLY these operational-resilience facts:\n" + json.dumps(evidence, default=str, ensure_ascii=False)},
            ],
        }
        headers = {"Authorization": f"Bearer {self.settings.groq_api_key}", "Content-Type": "application/json"}
        url = f"{self.settings.groq_base_url}/chat/completions"
        verify: Any = self.settings.groq_ca_bundle or self.settings.groq_verify_ssl
        try:
            with httpx.Client(timeout=60.0, verify=verify) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                commentary = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001
            return {
                "commentary": f"Commentary could not be generated (Groq request failed: {exc}). The deterministic facts remain available in the evidence panel.",
                "generated_at": _now(), "model": self.settings.groq_model, "evidence": evidence, "source": "error",
            }
        return {"commentary": commentary, "generated_at": _now(), "model": self.settings.groq_model, "evidence": evidence, "source": "groq"}


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()
