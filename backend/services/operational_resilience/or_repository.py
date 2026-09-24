"""Operational Resilience workbook loader.

Uses the same generic ExcelRepository class as Market Risk but a SEPARATE instance and
a SEPARATE workbook, so the two risk-stripe models never mix. This is the only data
source for the Operational Resilience path.
"""
from __future__ import annotations

from pathlib import Path

from backend.data.excel_repository import ExcelRepository

_or_repo: ExcelRepository | None = None


def get_or_repository(excel_path: str | Path | None = None) -> ExcelRepository:
    global _or_repo
    if _or_repo is None:
        if excel_path is None:
            from backend.config import get_settings

            excel_path = get_settings().or_excel_path
        _or_repo = ExcelRepository(excel_path)
        _or_repo.load()
    return _or_repo


def reset_or_repository() -> None:
    global _or_repo
    _or_repo = None
