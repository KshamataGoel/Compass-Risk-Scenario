"""Natural-language simulation parameter parser — the SECOND, separate Groq role.

This LLM call ONLY converts an English instruction into structured simulation
parameters. It never calculates VaR and never applies defaults (Python does that).
Its output is always validated in Python before it can reach the deterministic engine.

Two LLM roles exist and never mix:
  1. PARAMETER PARSER (here): natural language -> simulation parameters
  2. MANAGEMENT COMMENTARY (commentary_service): deterministic evidence -> prose
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pandas as pd

from backend.config import Settings
from backend.data.excel_repository import ExcelRepository
from backend.services.dimension_service import DimensionService
from backend.services.portfolio_service import PortfolioService

logger = logging.getLogger("parameter_parser")

# Current-screen defaults (used only when the sentence omits a parameter and the caller
# did not supply a current value).
DEFAULT_PORTFOLIO_TYPE = "Trading"
DEFAULT_RISK_HORIZON_DAYS = 1
DEFAULT_HISTORICAL_PNL_LOOKBACK = 5
DEFAULT_CONFIDENCE_LEVEL = 99
DEFAULT_COMMENTARY_DIMENSIONS = [
    "Asset Class", "Business", "Scenario", "Risk Factor", "Desk", "Book", "Instrument",
]

PARSER_SYSTEM_PROMPT = """You are a parameter extraction layer for a Market Risk Simulation application.

Your only task is to convert the user's natural-language simulation request into structured JSON.

Extract only parameters explicitly stated by the user.

Supported parameters:
portfolio_type
risk_horizon_days
historical_pnl_lookback
confidence_level
commentary_dimensions

Rules:
- 'past', 'historical', 'previous', 'last' refer to historical P&L lookback.
- 'forward', 'horizon', 'next', or phrases such as 'for 1 day' refer to risk horizon when clearly describing the VaR horizon.
- '99%', '98%', etc. refer to confidence level. Treat 'accuracy' in this market-risk context as confidence.
- 'Trading' refers to Trading portfolio type.
- commentary dimensions must only come from this supported list: Asset Class, Business, Scenario, Risk Factor, Desk, Book, Instrument. 'all'/'all dimensions' means all seven.
- Do not calculate VaR.
- Do not infer unsupported values.
- If a parameter is not stated, return null.
- Return valid JSON only, with exactly these keys: portfolio_type, risk_horizon_days, historical_pnl_lookback, confidence_level, commentary_dimensions.
- No prose. No markdown."""

# Dimension synonyms -> canonical names.
_DIM_CANON = {
    "asset class": "Asset Class", "assetclass": "Asset Class", "asset classes": "Asset Class", "asset": "Asset Class",
    "business": "Business", "business line": "Business", "business lines": "Business", "business unit": "Business", "business units": "Business",
    "scenario": "Scenario", "scenarios": "Scenario",
    "risk factor": "Risk Factor", "risk factors": "Risk Factor", "riskfactor": "Risk Factor",
    "desk": "Desk", "desks": "Desk",
    "book": "Book", "books": "Book",
    "instrument": "Instrument", "instruments": "Instrument",
}


class ParameterParserService:
    def __init__(self, settings: Settings, repo: ExcelRepository) -> None:
        self.settings = settings
        self.repo = repo

    # ----------------------------------------------------- allowed value sets
    def _total_trading_dates(self) -> int:
        pos = self.repo.get("position", required=False)
        if pos is not None and "asOfDate" in pos.columns:
            return int(pd.to_datetime(pos["asOfDate"], errors="coerce").dt.date.nunique())
        return 0

    def _allowed_portfolio_types(self) -> list[str]:
        return [o["value"] for o in PortfolioService(self.repo).available_portfolio_types() if o.get("available")]

    def _available_dimensions(self) -> list[str]:
        return [d["key"] for d in DimensionService(self.repo).available_dimensions() if d.get("available")]

    # ------------------------------------------------------------- LLM parse
    def parse(self, text: str) -> dict[str, Any] | None:
        """Call Groq to extract explicit parameters. Returns None on any failure."""
        if not text or not text.strip() or not self.settings.groq_configured:
            return None
        payload = {
            "model": self.settings.groq_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": PARSER_SYSTEM_PROMPT},
                {"role": "user", "content": text.strip()},
            ],
        }
        headers = {"Authorization": f"Bearer {self.settings.groq_api_key}", "Content-Type": "application/json"}
        url = f"{self.settings.groq_base_url}/chat/completions"
        verify: Any = self.settings.groq_ca_bundle or self.settings.groq_verify_ssl
        try:
            with httpx.Client(timeout=30.0, verify=verify) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
            return _extract_json(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Parameter parse failed: %s", exc)
            return None

    # ------------------------------------------------- validate + apply defaults
    def resolve(self, parsed: dict[str, Any] | None, current: dict[str, Any] | None) -> dict[str, Any]:
        """Validate parsed values, then fill gaps with current-screen values / defaults.

        Invalid LLM values are discarded and replaced by the default for that field.
        """
        parsed = parsed or {}
        current = current or {}
        total_dates = self._total_trading_dates()
        allowed_pt = self._allowed_portfolio_types()
        available_dims = self._available_dimensions()

        # Available horizon values (from config): H valid when H < total trading dates.
        allowed_horizons = [h for h in (1, 2, 5, 10) if 0 < h < max(total_dates, 1)]

        def default(key: str, fallback: Any) -> Any:
            v = current.get(key)
            return v if v is not None else fallback

        # ---- Portfolio type
        pt = parsed.get("portfolio_type")
        pt = pt if isinstance(pt, str) and pt in allowed_pt else None
        portfolio_type = pt if pt is not None else default("portfolio_type", DEFAULT_PORTFOLIO_TYPE)

        # ---- Risk horizon (must be a supported horizon option)
        h = parsed.get("risk_horizon_days")
        h = h if isinstance(h, int) and h in allowed_horizons else None
        risk_horizon = h if h is not None else default("forward_horizon_days", DEFAULT_RISK_HORIZON_DAYS)
        if risk_horizon not in allowed_horizons and allowed_horizons:
            risk_horizon = DEFAULT_RISK_HORIZON_DAYS if DEFAULT_RISK_HORIZON_DAYS in allowed_horizons else allowed_horizons[0]

        # ---- Historical P&L lookback (positive int within data availability; N observations
        #      need N + horizon valuation dates). Not restricted to the dropdown presets.
        max_lookback = max(0, total_dates - risk_horizon)
        lb = parsed.get("historical_pnl_lookback")
        lb = lb if isinstance(lb, int) and 2 <= lb <= max_lookback else None
        lookback = lb if lb is not None else default("lookback_days", DEFAULT_HISTORICAL_PNL_LOOKBACK)
        if not (isinstance(lookback, int) and 2 <= lookback <= max_lookback):
            lookback = min(DEFAULT_HISTORICAL_PNL_LOOKBACK, max_lookback) if max_lookback >= 2 else max_lookback

        # ---- Confidence level (supported discrete value or permitted 0<c<100 range)
        c = parsed.get("confidence_level")
        # The model sometimes returns a fraction (e.g. 0.98 for "98%"); normalise to a percent.
        if isinstance(c, (int, float)) and not isinstance(c, bool) and 0 < c <= 1:
            c = c * 100
        c = c if isinstance(c, (int, float)) and not isinstance(c, bool) and 0 < c < 100 else None
        confidence = c if c is not None else default("confidence_level", DEFAULT_CONFIDENCE_LEVEL)
        if not (isinstance(confidence, (int, float)) and 0 < confidence < 100):
            confidence = DEFAULT_CONFIDENCE_LEVEL

        # ---- Commentary dimensions (subset of the supported list; else all defaults)
        dims = _normalise_dimensions(parsed.get("commentary_dimensions"), available_dims)
        if not dims:
            cur_dims = current.get("dimensions")
            dims = cur_dims if cur_dims else [d for d in DEFAULT_COMMENTARY_DIMENSIONS if d in available_dims]

        resolved = {
            "portfolio_type": portfolio_type,
            "risk_horizon_days": int(risk_horizon),
            "historical_pnl_lookback": int(lookback),
            "confidence_level": (int(confidence) if float(confidence).is_integer() else float(confidence)),
            "commentary_dimensions": dims,
        }
        resolved["interpretation"] = (
            f"{portfolio_type} | {resolved['risk_horizon_days']}-Day Horizon | "
            f"{resolved['historical_pnl_lookback']} Historical P&L Observations | "
            f"{resolved['confidence_level']}% Confidence | {len(dims)} Commentary Dimensions"
        )
        return resolved

    def parse_and_resolve(self, text: str, current: dict[str, Any] | None) -> dict[str, Any]:
        parsed = self.parse(text)
        resolved = self.resolve(parsed, current)
        groq_ok = parsed is not None
        return {
            "parsed": parsed,
            "resolved": resolved,
            "interpretation": resolved["interpretation"],
            "source": "groq" if groq_ok else "fallback",
            "note": None if groq_ok else (
                "Could not interpret the natural-language request. Running with the displayed simulation parameters."
            ),
        }


def _extract_json(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    text = content.strip()
    # Strip ```json fences if present.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return None
    return None


def _normalise_dimensions(raw: Any, available: list[str]) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        key = item.strip().lower()
        if key in ("all", "all dimensions", "everything"):
            return [d for d in DEFAULT_COMMENTARY_DIMENSIONS if d in available]
        canon = _DIM_CANON.get(key)
        if canon and canon in available and canon not in out:
            out.append(canon)
    return out
