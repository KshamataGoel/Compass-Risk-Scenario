"""Persist a validated simulation result to the output workbook.

Governance: this saves ONLY the Python-calculated Simulation VaR taken from the
`simulation` block of the result. It never reads or writes the stored -$38m /
RMT001 value, and it never touches the source workbook — output goes to a separate
Market_Risk_Simulation_Output.xlsx. Each save appends a run row plus its P&L rows.
"""
from __future__ import annotations

import datetime as _dt
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

RUNS_SHEET = "simulation_runs"
PNL_SHEET = "pnl_distribution"


class OutputService:
    def __init__(self, output_path: str | Path) -> None:
        self.output_path = Path(output_path)

    def save_simulation(self, result: dict[str, Any]) -> dict[str, Any]:
        sim = result.get("simulation") or {}
        if not sim.get("available"):
            return {"saved": False, "message": sim.get("message") or "No calculated simulation to save."}

        params = result.get("simulation_parameters", {}) or {}
        portfolio = result.get("portfolio", {}) or {}
        util = ((result.get("thresholds") or {}).get("utilisation") or {})

        run_id = "SIMRUN-" + _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
        saved_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

        # Run summary — every value here is CALCULATED (from sim), never stored VaR.
        run_row = {
            "runId": run_id,
            "savedAt": saved_at,
            "portfolioType": params.get("portfolio_type"),
            "asOfDate": params.get("as_of_date"),
            "horizonDays": sim.get("horizon_days"),
            "lookbackDays": sim.get("lookback_days"),
            "confidenceLevel": sim.get("confidence_level"),
            "methodology": sim.get("methodology"),
            "simulationVar": sim.get("simulation_var"),
            "previousSimulationVar": sim.get("previous_simulation_var") if sim.get("previous_available") else None,
            "varChange": sim.get("var_change"),
            "warningThreshold": util.get("warning_threshold"),
            "varUtilisationPct": util.get("utilisation_pct"),
            "worstHistoricalPnl": sim.get("worst_pnl"),
            "bestHistoricalPnl": sim.get("best_pnl"),
            "averageHistoricalPnl": sim.get("average_pnl"),
            "pnlObservationCount": sim.get("observation_count"),
            "portfolioMarketValue": portfolio.get("total_market_value_bcy"),
            "positionCount": portfolio.get("position_count"),
            "unit": sim.get("unit"),
        }

        pnl_rows = []
        for r in sim.get("pnl_distribution", []) or []:
            pnl_rows.append(
                {
                    "runId": run_id,
                    "startDate": r.get("start_date"),
                    "endDate": r.get("end_date"),
                    "startingPortfolioValue": r.get("starting_portfolio_value"),
                    "endingPortfolioValue": r.get("ending_portfolio_value"),
                    "historicalPnl": r.get("historical_pnl"),
                }
            )

        runs_df, pnl_df = self._read_existing()
        runs_df = pd.concat([runs_df, pd.DataFrame([run_row])], ignore_index=True)
        if pnl_rows:
            pnl_df = pd.concat([pnl_df, pd.DataFrame(pnl_rows)], ignore_index=True)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(self.output_path, engine="openpyxl") as writer:
            runs_df.to_excel(writer, sheet_name=RUNS_SHEET, index=False)
            pnl_df.to_excel(writer, sheet_name=PNL_SHEET, index=False)

        return {
            "saved": True,
            "run_id": run_id,
            "saved_at": saved_at,
            "path": str(self.output_path),
            "simulation_var": sim.get("simulation_var"),
            "runs_in_file": int(len(runs_df)),
            "message": f"Saved calculated Simulation VaR to {self.output_path.name} (run {run_id}).",
        }

    def _read_existing(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if not self.output_path.exists():
            return pd.DataFrame(), pd.DataFrame()
        try:
            xls = pd.ExcelFile(self.output_path, engine="openpyxl")
            runs = pd.read_excel(xls, RUNS_SHEET) if RUNS_SHEET in xls.sheet_names else pd.DataFrame()
            pnl = pd.read_excel(xls, PNL_SHEET) if PNL_SHEET in xls.sheet_names else pd.DataFrame()
            return runs, pnl
        except Exception:
            # Corrupt/locked file — start fresh rather than fail the save silently mid-write.
            return pd.DataFrame(), pd.DataFrame()

    def list_runs(self) -> dict[str, Any]:
        runs, _ = self._read_existing()
        return {
            "path": str(self.output_path),
            "exists": self.output_path.exists(),
            "runs": runs.where(pd.notna(runs), None).to_dict("records") if not runs.empty else [],
        }
