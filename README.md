# Market Risk Scenario Simulation

An interactive Market Risk Scenario Simulation over the supplied Excel workbook. The
workbook is the **only** data source; every displayed value is either retrieved
(`STORED`), deterministically calculated from workbook data (`CALCULATED`), or
explicitly marked `UNAVAILABLE`. Groq is used **only** to phrase the final
management commentary from facts the Python backend has already derived — it never
calculates a metric or invents data.

```
DATA → CALCULATION → METRICS → DIMENSIONS → LLM SUMMARY
```

## Architecture

| Layer | Stack | Role |
|---|---|---|
| Backend | Python · FastAPI · pandas · openpyxl | Loads the workbook, runs all deterministic risk logic, builds the governed evidence JSON |
| Frontend | Next.js · TypeScript · Tailwind | Simulation panel, metrics, charts, dimension analysis, lineage, commentary |
| LLM | Groq (via backend only) | Natural-language management summary from the evidence JSON |

Key documents: [`SCHEMA_MAP.md`](SCHEMA_MAP.md) (workbook schema & derived facts) and
[`PROMPT.md`](PROMPT.md) (the full build specification).

## Data source

`Database/Market_Risk_Case2_2Week_History_Database.xlsx` — 28 sheets. Column headers
carrying a literal ` (FK)` suffix are normalised on load; original headers are kept
for lineage. Latest snapshot is `2026-08-27` (10 positions, all Trading book).

## Prerequisites (this machine)

- Python 3.12 (`python` on PATH).
- Node.js is at `C:\Users\703313047\node`. `npm.ps1` is blocked by execution policy,
  so use **`npm.cmd`** (shown below).

## 1. Backend

```bash
cd "C:\Users\703313047\OneDrive - Genpact\Desktop\Projects\Compass"
python -m pip install -r backend/requirements.txt
```

Optionally enable commentary generation — copy `backend/.env.example` to
`backend/.env` and set `GROQ_API_KEY` (and optionally `GROQ_MODEL`). Without a key
the app still works fully; only the natural-language summary is disabled and shown as
"LLM not configured".

Run:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend endpoints: `/api/health`, `/api/data-health`, `/api/config/options`,
`POST /api/simulation`, `/api/metrics`, `/api/risk-factors`, `/api/scenarios`,
`POST /api/commentary`, `POST /api/save-simulation`, `/api/saved-simulations`.

## 2. Frontend

Using this machine's Node install (PowerShell):

```powershell
cd "C:\Users\703313047\OneDrive - Genpact\Desktop\Projects\Compass\frontend"
& "C:\Users\703313047\node\npm.cmd" install
& "C:\Users\703313047\node\node.exe" "node_modules\next\dist\bin\next" dev -p 3000
```

Open http://localhost:3000. The frontend proxies `/api/*` to the backend
(`NEXT_PUBLIC_API_BASE`, default `http://localhost:8000` — see `frontend/next.config.js`).

## 3. Tests

```bash
cd "C:\Users\703313047\OneDrive - Genpact\Desktop\Projects\Compass"
python -m pytest backend/tests -q
```

Covers Excel loading & FK normalisation, latest-position selection, trading-book
filtering, risk-factor mapping, IR bps / FX % movements, VaR retrieval & utilisation,
component-VaR summation, scenario aggregation at position grain (no double counting),
dimension filtering, Groq payload construction, and unavailable-metric handling.

## Simulation VaR — calculated in real time (see the CORRECTION in `PROMPT.md`)

After **Run Scenario Simulation**, VaR is **calculated at request time** from the
portfolio's own market-value history — it does **not** read the stored
`risk_metric_mr_obs` / `risk_metric_obs` (−$38m RMT001) value:

```
PortfolioValue(date) = SUM(position.marketValueBcy)               (position grain)
HistoricalPnL(t)     = PortfolioValue(t) − PortfolioValue(t−H)    (H = risk horizon)
lower_tail_pnl       = np.quantile(pnl, 1 − confidence, method="lower")
SimulationVaR        = max(0, −lower_tail_pnl)   # loss ⇒ +VaR; gain ⇒ 0
```

**Historical P&L Lookback = N observations** (not N dates): N observations at horizon H
need N+H ordered valuation dates. **Simulation VaR Trend** recomputes VaR point-in-time
for the latest 6 valid as-of dates (each uses only data up to that date) and classifies
the move (Increased / Steady / Decreased, ±5% threshold). **VaR Tail Loss Contribution**
decomposes the single selected tail-P&L observation into per-position → by-exposure →
by-asset-class contributions (reconciled to the net tail P&L) with a deterministic main
driver — this is a decomposition of one historical observation, not Marginal/Component VaR.

The four drivers — Portfolio Type, Risk Horizon, Historical Lookback, **Confidence
Level** — are genuine user inputs (`{portfolio_type, forward_horizon_days,
lookback_days, confidence_level}`); the backend never overrides them with the stored
`risk_metric_mr` config. Previous Simulation VaR uses the same calculation one as-of
period earlier and is `UNAVAILABLE` (never substituted) when history is too short. The
`simulation` logger prints every step (portfolio value by date, P&L, sorted P&L,
selected quantile, final VaR) for manual validation. Success criterion (spec §23):
zeroing the stored RMT001 value must not change the result — covered by
`test_simulation_var_independent_of_stored_rmt001`.

> Note: with the POC's ~9–10 P&L observations and the mandated `method="lower"`, the
> 1% and 5% tails can land on the same worst observation, so 95% vs 99% may coincide —
> mathematically correct for such a small sample. The P&L Distribution table and debug
> logs make the selected tail point explicit.

## Save Simulation (§20–21)

**Run** only calculates — it never writes. **Save Simulation** (button under the
Historical Simulation P&L section) persists the *calculated* result via
`POST /api/save-simulation` to a **separate** workbook
`output/Market_Risk_Simulation_Output.xlsx` (`SIMULATION_OUTPUT_PATH` to override) —
the source workbook is never modified. Each save appends a row to `simulation_runs`
(runId, params, Simulation VaR, previous, change, threshold, utilisation, worst/best/avg
P&L, observation count) and its P&L rows to `pnl_distribution`. Only values from the
calculated `simulation` block are written; the stored −$38m is never persisted
(`test_save_simulation_persists_calculated_var`).

## Governance guarantees

- **No fabrication.** Missing information surfaces as "Not available from current data
  model" / "Not independently calculable from current data model".
- **Exposure ≠ contribution.** Risk factors are "Associated"; asset-class charts are
  "Market Value by …", never "VaR contribution".
- **Trading only** (all `tradingBookFlag = Y`). Risk horizon H is available when the
  workbook has more than H trading snapshots (1/2/5 available, 10 not).
- **No double counting.** All market-value aggregation is at the position grain.
- **Auditability.** The exact evidence JSON sent to Groq is shown under "View
  Commentary Evidence" (calculated Simulation VaR only, no stored −$38m); every metric
  has a "View Data Lineage" panel.
