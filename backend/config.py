"""Central configuration. All external secrets come from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Repository root = parent of the backend package.
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

# Load backend/.env by EXPLICIT absolute path so it works no matter what the current
# working directory is (uvicorn, the .bat launcher, python -c, tests, etc.). Relying on
# load_dotenv()'s directory search silently fails to find it in some launch contexts.
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    """Application settings sourced from environment / sensible local defaults."""

    def __init__(self) -> None:
        # --- Excel workbook (the ONLY data source) ---
        default_wb = PROJECT_ROOT / "Database" / "Market_Risk_Case2_2Week_History_Database.xlsx"
        self.excel_path: Path = Path(os.getenv("EXCEL_WORKBOOK_PATH", str(default_wb)))

        # --- Simulation output workbook (written only on explicit Save, never the source) ---
        default_out = PROJECT_ROOT / "output" / "Market_Risk_Simulation_Output.xlsx"
        self.simulation_output_path: Path = Path(os.getenv("SIMULATION_OUTPUT_PATH", str(default_out)))

        # --- Operational Resilience workbook (separate risk-stripe model; read-only source) ---
        default_or = PROJECT_ROOT / "Database" / "Operational_Resilience_POC_Database.xlsx"
        self.or_excel_path: Path = Path(os.getenv("OR_WORKBOOK_PATH", str(default_or)))

        # --- Groq (commentary generation ONLY) ---
        self.groq_api_key: str | None = os.getenv("GROQ_API_KEY")
        self.groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        # Corporate TLS interception: point GROQ_CA_BUNDLE at your org's root CA .pem,
        # or set GROQ_VERIFY_SSL=false to skip verification (POC networks only).
        self.groq_ca_bundle: str | None = os.getenv("GROQ_CA_BUNDLE") or None
        self.groq_verify_ssl: bool = os.getenv("GROQ_VERIFY_SSL", "true").strip().lower() not in ("false", "0", "no")

        # --- CORS ---
        origins = os.getenv("FRONTEND_ORIGINS", "http://localhost:3000")
        self.frontend_origins: list[str] = [o.strip() for o in origins.split(",") if o.strip()]

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
