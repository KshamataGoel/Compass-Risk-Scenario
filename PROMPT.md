# Market Risk Scenario Simulation — Build Spec (Source Prompt)

> Saved verbatim per instruction "keep saving prompt as well". This is the authoritative build specification.
> **See the CORRECTION section at the bottom — it overrides §9/§11 for the Current/Simulation VaR.**

You are a senior full-stack engineer building a Market Risk Scenario Simulation application.

## Stack
**BACKEND**: Python, FastAPI, pandas, openpyxl for Excel access/calculation where required.
**FRONTEND**: Node.js, Next.js, TypeScript, Tailwind CSS, shadcn/ui where useful.
**LLM**: Groq API — LLM is ONLY for final management commentary generation.
- Groq must NEVER calculate Market Risk metrics.
- Groq must NEVER invent data, dimensions, scenarios, business lines, risk factors, asset classes, values, thresholds, exposures, or explanations not supplied by the Python backend.

## 1. CRITICAL DATA GOVERNANCE RULE
The supplied Excel workbook is the ONLY DATA SOURCE.
Do NOT: create mock/synthetic data, hard-code portfolio names / asset classes / business lines / scenarios / risk factors / risk metrics / instruments, invent relationships / DB columns, infer nonexistent relationships, introduce another data source, use internet/external market data, or create values just to make the UI look complete.
Every selectable/displayed/calculated/summary fact must be traceable to the Excel workbook.
If information cannot be derived, show: "Not available from current data model". Do NOT fabricate.

## 2. EXCEL DATABASE
Use the supplied Market Risk Excel workbook as the DB. Read sheet & column names dynamically. Do not rename/restructure entities.
Important entities: trade, position, instrument, asset_class, product, risk_factor, risk_factor_obs, instrument_risk_factor_map, risk_metric, risk_metric_mr, risk_metric_mr_obs, risk_metric_obs, risk_measure, risk, portfolio_hierarchy, desk, book, scenario_mr, risk_factor_shock, risk_pnl_record, sensitivity, model, risk_threshold, risk_threshold_breach, and the rest present in the workbook.
The actual workbook structure ALWAYS takes precedence. Inspect first. Do not assume a column exists just because mentioned conceptually.

## 3. APPLICATION PURPOSE — MARKET RISK SCENARIO SIMULATION
User configures the risk analysis then sees: (1) Selected simulation parameters, (2) Associated Market Risk metrics, (3) Risk-factor movements, (4) Portfolio/exposure info, (5) Scenario info, (6) Dimension-level analysis, (7) Final management summary.
Visual flow: User Selection → Portfolio Scope → Current Positions → Instruments → Risk Factors → Historical Risk Factor Observations → Historical Movements → Scenario/Risk Calculations → Risk Metrics → Dimension Analysis → Management Commentary.

## 4. SIMULATION INPUT PANEL
Title: "Market Risk Scenario Simulation".
- **A. Forward Days** — label "Risk Horizon" (1/5/10 Days). Do NOT assume every horizon is supported; determine from data/model. If only 1-day VaR supported, identify 1 Day as available. Don't manufacture 5/10-day VaR unless a mathematically valid transformation is explicitly implemented and clearly labelled.
- **B. Portfolio Type** — label "Portfolio Type", derived from data (e.g. trade.tradingBookFlag). Trading = tradingBookFlag=Y. Don't assume Non-Trading exists; if none, show unavailable / "No positions available for selected portfolio type."
- **C. Lookback Period** — label "Historical Lookback". POC ≈ 2 weeks / 10 trading days. Derive from risk_factor_obs.observationDate. Don't manufacture 1-month/1-year/2-year. E.g. 5 / 10 Trading Days if supported.
- **D. Commentary Dimensions** — multi-select "Management Commentary Dimensions", default SELECT ALL available. Candidates: Asset Class, Business/Business Line, Scenario, Risk Factor, Desk, Book, Instrument — only if derivable from workbook relationships.
  - Asset Class: position → instrument → asset_class
  - Risk Factor: position → instrument → instrument_risk_factor_map → risk_factor
  - Scenario: risk_metric_mr → scenarioSetId → scenario_mr
  - Business: only through available relationships (risk/risk_metric → business-unit structures)
  - Desk: position.deskId → desk; Book: position.bookId → book

## 5. RUN SIMULATION
Primary button "Run Scenario Simulation". On click DO NOT immediately call Groq. First run all deterministic Python. Show progress: 1 Loading portfolio, 2 Identifying current positions, 3 Mapping instruments, 4 Mapping risk factors, 5 Loading historical market observations, 6 Calculating historical movements, 7 Retrieving risk metrics, 8 Analysing selected dimensions, 9 Preparing management summary. Only step 9 involves Groq.

## 6. DETERMINE CURRENT PORTFOLIO
Use latest applicable position.asOfDate for selected portfolio. Use trade.tradingBookFlag for Trading/Non-Trading scope. Join on actual keys (position.tradeId → trade.tradeId). Show: As Of Date, #Positions, #Trades, #Instruments, Books, Desks where derivable.

## 7. RISK FACTOR EXPOSURE
Trace position.instrumentId → instrument.instrumentId → instrument_risk_factor_map.instrumentId → .riskFactorId → risk_factor.riskFactorId. Proves EXPOSURE/ASSOCIATION only, NOT "Main VaR Driver". Use "Associated Risk Factors" unless contribution is in DB.

## 8. HISTORICAL RISK FACTOR OBSERVATIONS
Use risk_factor_obs. Per factor sort by observationDate, calc 1-day movements. Interest Rates: differences in bps (4.34%→4.38% = +4bps). FX/price: percentage (current/previous)-1. Deterministic Python only; Groq must not calculate.

## 9. HISTORICAL SIMULATION LOGIC
Separate Current Portfolio from Historical Market Movements. Concept: CURRENT POSITIONS + HISTORICAL RISK-FACTOR MOVEMENTS = HYPOTHETICAL PORTFOLIO P&L. Don't just calc VaR from historical position MV changes and call it Historical Simulation VaR. If workbook lacks pricing/revaluation info to independently revalue, do NOT invent a pricing model. Instead: use stored calculated metrics; calc only what's legitimately calculable; show unavailable as "Not independently calculable from current data model". Distinguish A retrieved/stored, B deterministically calculated, C unavailable.

## 10. METRICS SECTION — BEFORE SUMMARY
Show "Market Risk Metrics" before any commentary. Display all relevant supported metrics for the scope. Cards/table/charts. Possible (only when available): Current VaR, Previous VaR, VaR Change, VaR Utilisation %, Warning Threshold, Stress Scenario P&L, Sensitivity, Position Market Value, #Positions, #Trades, #Instruments, Risk Factor Count, Scenario Count, Threshold/Breach info. No empty fake cards.

## 11. CURRENT VAR
Use the appropriate MR metric observation table. POC current Trading VaR ≈ -$38m — do NOT hard-code, retrieve. Latest observationDateTime. Display: Current VaR, As-of Date, Risk Horizon, Confidence Level, Methodology, Lookback, Portfolio Type. Config from risk_metric_mr; output from the metric observation entity. Distinction: risk_metric_mr = config, risk_metric_mr_obs = observed result, risk_factor_obs = historical market variables. Don't mix.

## 12. VAR UTILISATION
VaR Utilisation = ABS(Current VaR)/Applicable Warning Threshold. Use risk_threshold + appropriate metric relationship, not an arbitrary threshold. Show Current VaR, Warning Threshold, Utilisation %. Derive from workbook; don't hard-code.

## 13. TREND
Where multiple observations exist, show VaR trend chart. X=observationDateTime, Y=metricValue. Compare Previous/Current/Change. Available data only.

## 14. ASSOCIATED RISK FACTORS
Section "Associated Risk Factors". Columns: Risk Factor, Type, Subtype, Tenor, Currency, Latest Observed Value, Historical Min, Historical Max, Latest 1-Day Movement. From risk_factor + risk_factor_obs + instrument/position relationships.

## 15. ASSET CLASS DIMENSION
Derive position.instrumentId → instrument → instrument.assetClassId → asset_class.assetClassId. Show actual asset classes in portfolio. Metrics: Position Count, Instrument Count, Market Value. Don't claim "VaR contribution by asset class" unless valid measure. Label accurately ("Market Value by Asset Class").

## 16. BUSINESS DIMENSION
Derive business only via actual relationships in risk_metric, risk, hsbc_global_Business_Unit, portfolio_hierarchy etc. Don't invent hierarchy. Show Business Unit, Relevant Risk Metrics, Portfolio/Risk association where supported. Don't write "most business lines" unless data demonstrates it deterministically.

## 17. SCENARIO DIMENSION
Trace risk_metric_mr.riskMetricId → .scenarioSetId → scenario_mr.scenarioSetId, then scenario_mr → risk_factor_shock → risk_factor. Show Scenario Name, Type, Date, Risk Factor, Shock Type, Shock Value, Shock Unit. Use risk_pnl_record where scenario P&L exists. Don't confuse Historical Simulation movements with explicit Stress Scenario shocks.

## 18. STRESS SCENARIO P&L
Use risk_pnl_record. Aggregate amountBaseCcy at a grain avoiding duplication. Show Total Scenario P&L, P&L by component, by book/position/scenario where supported. Don't call Stress Scenario P&L "VaR".

## 19. SENSITIVITY
Use sensitivity where available. Show Sensitivity Value, Currency, Associated Risk Metric, Risk Model. Don't interpret sensitivity as VaR contribution unless data supports.

## 20. METRIC LINEAGE / TRACEABILITY
Every metric gets optional "View Data Lineage"/info icon. E.g. Current VaR ← risk_metric_mr_obs.metricValue; config risk_metric_mr; threshold risk_threshold; historical risk_factor_obs; portfolio position+trade; risk factor instrument_risk_factor_map+risk_factor.

## 21. DIMENSION ANALYSIS SECTION
After metrics show "Dimension Analysis". Only render user-selected dimensions. Each: concise KPI, chart/table, data-supported observations. No Groq narrative yet.

## 22. MANAGEMENT SUMMARY
Only AFTER: 1 Simulation Parameters, 2 Portfolio Overview, 3 Market Risk Metrics, 4 Historical Market Movements, 5 Dimension Analysis — show "Management Summary" with button "Generate Management Summary" (invokes Groq).

## 23. GROQ ARCHITECTURE
Groq must NOT receive raw workbook. Python builds a controlled structured JSON: simulation_parameters, portfolio, metrics, risk_factors, historical_movements, asset_class_analysis, business_analysis, scenario_analysis, stress_pnl, sensitivity, selected_commentary_dimensions. Only deterministically derived info. Send this JSON to Groq.

## 24. GROQ SYSTEM PROMPT (strict)
"You are a Market Risk management commentary generator. You will receive structured JSON produced from an approved Market Risk database. Your task is ONLY to summarize the supplied facts. STRICT RULES: 1 Never invent a number. 2 Never calculate a new risk metric. 3 Never invent a risk factor. 4 Never invent a scenario. 5 Never invent a business line. 6 Never invent an asset class. 7 Never introduce external market knowledge. 8 Never attribute causality unless supported. 9 Exposure ≠ contribution. 10 Don't call something a 'main driver' merely because exposure exists. 11 Don't state a scenario caused VaR unless explicitly supported. 12 Use only dimensions requested by the user. 13 If evidence insufficient, omit rather than guess. 14 Keep commentary concise and management-friendly. 15 Preserve metric signs and units correctly."

## 25. TARGET COMMENTARY STYLE
Style example (do NOT hard-code): "Trading VaR (1d, 2-week lookback) was $X, representing Y% utilisation of the applicable warning threshold. The portfolio has exposure to [supported risk-factor categories]. [Selected dimension observations]. Under [scenario], the recorded scenario P&L was [value]." Generate only supported statements. If not proven that IR/FX mainly drove VaR, say "The portfolio has exposures to interest-rate and FX risk factors."

## 26. USER-SELECTED COMMENTARY DIMENSIONS
Groq respects selected dimensions. Default ALL supported. Don't discuss Desk/Book merely because present in backend JSON.

## 27. UI DESIGN
Professional banking/risk interface, not overly decorative. Page: Title → [Risk Horizon][Portfolio Type][Historical Lookback][Commentary Dimensions ▼] → [Run Scenario Simulation] → Simulation Parameters → Portfolio Overview → Market Risk Metrics → VaR Trend → Associated Risk Factors → Historical Market Movements → Dimension Analysis → Management Summary.

## 28. DATA VALIDATION
At startup: load workbook, discover sheets, validate required columns, relationship keys, date fields, numeric fields, report missing deps. Don't silently substitute. Endpoint GET /api/data-health returns loaded sheets, row counts, missing columns, relationship issues, latest dates, historical observation range.

## 29. BACKEND SERVICE DESIGN (modular)
backend/ main.py, config.py; data/ excel_repository.py, schema_validator.py; services/ portfolio_service.py, risk_factor_service.py, historical_simulation_service.py, risk_metric_service.py, threshold_service.py, scenario_service.py, sensitivity_service.py, dimension_service.py, commentary_service.py, lineage_service.py; models/ request_models.py, response_models.py; tests/. Don't put all calc logic in one file.

## 30. FRONTEND STRUCTURE
frontend/ app/; components/ SimulationControls, SimulationParameters, PortfolioOverview, MetricCards, VarTrend, RiskFactorTable, HistoricalMovements, DimensionSelector, DimensionAnalysis, ScenarioAnalysis, ManagementSummary, DataLineage; services/ api.ts. Reusable components.

## 31. API DESIGN
GET /api/config/options (valid selections from DB); POST /api/simulation {forward_days, portfolio_type, lookback_days, dimensions} → deterministic results; GET /api/metrics; GET /api/risk-factors; GET /api/scenarios; GET /api/data-health; POST /api/commentary (accepts already-validated structured simulation result, doesn't re-read/invent).

## 32. CALCULATION STATUS
Each metric includes metadata: {metric_name, value, unit, status, source}. Status: STORED | CALCULATED | UNAVAILABLE. E.g. Current VaR STORED; VaR Utilisation CALCULATED; full HS revaluation UNAVAILABLE.

## 33. NO DOUBLE COUNTING
Careful with many-to-many (instrument ↔ instrument_risk_factor_map ↔ risk_factor). Don't aggregate position MV after joining multiple risk factors. Aggregate at original position grain; use mapping tables only for classification.

## 34. GROQ CONFIGURATION
Read Groq creds from env (GROQ_API_KEY). Never in frontend JS. All Groq calls via Python backend. Provide .env.example, never commit real creds. GROQ_MODEL configurable via env.

## 35. AUDITABILITY
Retain per commentary: simulation parameters, selected dimensions, deterministic metrics sent to Groq, timestamp, generated commentary. Collapsible "View Commentary Evidence" showing exact facts supplied to Groq.

## 36. TESTING
Test: Excel loading, latest-position selection, Trading Book filtering, risk-factor mapping, historical observation ordering, IR bps movement, FX percentage movement, threshold matching, VaR utilisation, scenario aggregation, position double-counting prevention, dimension filtering, Groq payload construction, unavailable metric handling. Most importantly: no value appears in API response unless traceable to workbook data or a deterministic calc from it.

## 37. FINAL IMPLEMENTATION ORDER
1 Inspect workbook. 2 Produce internal schema map (sheet, primary id, FK-like columns, relationships). 3 Excel repository. 4 Deterministic calculations. 5 APIs. 6 Frontend. 7 Groq commentary last. Do NOT start by designing mock UI data.

## 38. NON-NEGOTIABLE PRINCIPLE
DATA → CALCULATION → METRICS → DIMENSIONS → LLM SUMMARY. Never LLM → DATA/CALCULATION. The LLM is a language layer only. Every factual statement in the final summary must be explainable from the structured evidence supplied by the backend.

---

# CORRECTION — Real-time Simulation VaR (OVERRIDES §9 and §11 for Current VaR)

The Current VaR must NOT be read from `risk_metric_mr_obs.metricValue` / `risk_metric_obs.metricValue` (the stored −$38m from RMT001). After the user clicks **Run Scenario Simulation**, VaR is **calculated in Python** from position history using the user-selected Portfolio Type, Risk Horizon, Historical Lookback and Confidence Level. This explicitly reverses the original §9 instruction ("do NOT compute VaR from position market-value changes").

1. **Calculated, not stored.** No dependency on `38000000` / RMT001 latest metricValue anywhere: Current/Simulation VaR, VaR Change, VaR Utilisation, simulation summary, KPI cards, commentary payload.
2. **Portfolio value history** — `PortfolioValue(date) = SUM(position.marketValueBcy)` for the selected portfolio (positions → trade.tradingBookFlag). Workbook values only.
3. **Lookback** — use the latest N trading dates. If N > available dates → "Insufficient historical data." Never manufacture history.
4. **Horizon H** — `HistoricalPnL(t) = PortfolioValue(t) − PortfolioValue(t−H)` using trading observations (not calendar days).
5. **P&L distribution** — rows: start_date, end_date, starting_portfolio_value, ending_portfolio_value, historical_pnl. Visible in the UI for validation.
6. **VaR from confidence** — `SimulationVaR = ABS(np.quantile(pnl_array, 1 − confidence_decimal, method="lower"))`.
7. **Card** — rename to **Simulation VaR**, status **CALCULATED**; lineage = position.asOfDate, position.marketValueBcy, trade.tradingBookFlag, selected lookback/horizon/confidence.
8. **Previous Simulation VaR** — same params, one as-of period earlier; **UNAVAILABLE** if insufficient data (never substitute stored −$37.8m).
9. **VaR Change** = Current − Previous (CALCULATED, only if previous available).
10. **VaR Utilisation** = SimulationVaR / `risk_threshold.thresholdValueHigh` × 100 (threshold is INPUT/REFERENCE; VaR is the calculated one).
11. **Remove stored −$38m from the main screen** (no Reference VaR yet). Replace the stored `risk_metric_mr_obs` VaR trend with a **Historical Simulation P&L** chart (x=end_date, y=historical_pnl) plus the selected VaR loss point.
12. **Metrics section** now shows calculated values first: Simulation VaR, Previous Simulation VaR, VaR Change, Portfolio Market Value, Position/Trade/Instrument Count, Warning Threshold (REFERENCE), VaR Utilisation, Worst/Best/Average Historical P&L, P&L Observation Count, Risk Factor Count.
13. **Request** carries `{portfolio_type, forward_horizon_days, lookback_days, confidence_level}`. Confidence is a real user input in the top control area — do NOT override it with `risk_metric_mr.confidenceLevel`. Backend must use the request values, not the stored `risk_metric_mr` config.
14. **Debug logging** (until validated): log portfolio type, horizon, lookback, confidence, selected trading dates, portfolio value by date, historical P&Ls, sorted P&Ls, selected quantile, final Simulation VaR.
15. **Keep unchanged for now**: Associated Risk Factors, Historical Market Movements, Asset Class / Desk / Book / Instrument analysis, Scenario tables, Sensitivity table.
16. **Success criterion**: deleting/changing stored RMT001 −$38m must NOT change the Simulation VaR. If it does, the implementation is wrong.
