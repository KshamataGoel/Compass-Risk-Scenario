"""Excel repository — the single source of truth.

Loads the supplied Market Risk workbook once, discovers sheets and columns
dynamically, and exposes read-only, normalised access to every entity.

Governance rules enforced here:
  * No data is invented. Only what the workbook contains is returned.
  * Column headers carrying a literal ' (FK)' suffix are normalised to clean
    names; the original headers are retained for lineage display.
  * Sheet lookups are case-insensitive so the exact casing in the workbook
    (e.g. 'hsbc_global_Business_Unit') does not have to be memorised.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any

import pandas as pd

_FK_SUFFIX = re.compile(r"\s*\(FK\)\s*$", re.IGNORECASE)


def _normalise_column(name: str) -> str:
    """Strip a trailing ' (FK)' marker and surrounding whitespace."""
    return _FK_SUFFIX.sub("", str(name)).strip()


class ExcelRepository:
    """In-memory, read-only view over the workbook."""

    def __init__(self, excel_path: str | Path) -> None:
        self.excel_path = Path(excel_path)
        self._lock = threading.Lock()
        self._frames: dict[str, pd.DataFrame] = {}
        self._sheet_lookup: dict[str, str] = {}          # lower-case -> actual sheet name
        self._original_columns: dict[str, list[str]] = {}  # actual sheet name -> raw headers
        self._loaded = False

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            if not self.excel_path.exists():
                raise FileNotFoundError(
                    f"Workbook not found at {self.excel_path}. "
                    "The application requires the supplied Market Risk workbook."
                )
            xls = pd.ExcelFile(self.excel_path, engine="openpyxl")
            for sheet in xls.sheet_names:
                raw = pd.read_excel(xls, sheet_name=sheet, engine="openpyxl")
                self._original_columns[sheet] = [str(c) for c in raw.columns]
                raw.columns = [_normalise_column(c) for c in raw.columns]
                # Trim whitespace on string cells (defensive; workbook is clean).
                for col in raw.columns:
                    if raw[col].dtype == object:
                        raw[col] = raw[col].map(lambda v: v.strip() if isinstance(v, str) else v)
                self._frames[sheet] = raw
                self._sheet_lookup[sheet.lower()] = sheet
            self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    # -------------------------------------------------------------- discovery
    @property
    def sheet_names(self) -> list[str]:
        self._ensure_loaded()
        return list(self._frames.keys())

    def has_sheet(self, name: str) -> bool:
        self._ensure_loaded()
        return name.lower() in self._sheet_lookup

    def original_columns(self, name: str) -> list[str]:
        self._ensure_loaded()
        actual = self._sheet_lookup.get(name.lower())
        return list(self._original_columns.get(actual, [])) if actual else []

    def columns(self, name: str) -> list[str]:
        df = self.get(name, required=False)
        return list(df.columns) if df is not None else []

    # ----------------------------------------------------------------- access
    def get(self, name: str, required: bool = True) -> pd.DataFrame | None:
        """Return a *copy* of the sheet as a DataFrame (clean column names)."""
        self._ensure_loaded()
        actual = self._sheet_lookup.get(name.lower())
        if actual is None:
            if required:
                raise KeyError(f"Sheet '{name}' is not present in the workbook.")
            return None
        return self._frames[actual].copy()

    def get_records(self, name: str, required: bool = True) -> list[dict[str, Any]]:
        df = self.get(name, required=required)
        if df is None:
            return []
        return df.where(pd.notna(df), None).to_dict(orient="records")

    def row_count(self, name: str) -> int:
        df = self.get(name, required=False)
        return 0 if df is None else len(df)

    # -------------------------------------------------------------- utilities
    def latest_value(self, name: str, date_col: str) -> Any:
        """Maximum value of a (date-like) column across a sheet."""
        df = self.get(name, required=False)
        if df is None or date_col not in df.columns or df.empty:
            return None
        series = pd.to_datetime(df[date_col], errors="coerce")
        return series.max()


# --------------------------------------------------------------- singleton
_repository: ExcelRepository | None = None


def get_repository(excel_path: str | Path | None = None) -> ExcelRepository:
    """Return the process-wide repository, creating it on first use."""
    global _repository
    if _repository is None:
        if excel_path is None:
            from backend.config import get_settings

            excel_path = get_settings().excel_path
        _repository = ExcelRepository(excel_path)
        _repository.load()
    return _repository


def reset_repository() -> None:
    """Testing helper — drop the cached singleton."""
    global _repository
    _repository = None
