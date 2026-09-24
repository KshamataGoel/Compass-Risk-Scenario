# Market Risk Workbook — Internal Schema Map

Source: `Database/Market_Risk_Case2_2Week_History_Database.xlsx` — 28 sheets. **This is the only data source.**

> NOTE: Every column header in the workbook that is a foreign key carries a literal ` (FK)` suffix
> (e.g. `riskFactorId (FK)`). The repository strips ` (FK)` and trailing spaces on load, so code uses
> clean names (`riskFactorId`). Original headers are retained for lineage display.

## Core entities, primary ids, and FK links

| Sheet | Rows | Primary id | Key FKs / links |
|---|---|---|---|
| `position` | 100 | positionId (10× over 10 dates) | tradeId→trade, instrumentId→instrument, bookId→book, deskId→desk |
| `trade` | 10 | tradeId | instrumentId→instrument, bookId, deskId; **tradingBookFlag = 'Y' (all)** |
| `instrument` | 5 | instrumentId | assetClassId→asset_class |
| `asset_class` | 3 | assetClassId | IR / FX / PM |
| `product` | 5 | productId | instrumentId→instrument |
| `risk_factor` | 7 | riskFactorId | RF001-003,006,007 = IR; RF004 = Precious Metal; RF005 = FX |
| `risk_factor_obs` | 70 | riskFactorObsId | riskFactorId; 7 factors × 10 dates (2026-08-14 … 2026-08-27); observedValue, observationUnit (%, USD/oz, FX Rate) |
| `instrument_risk_factor_map` | 12 | instrumentRiskFactorMapId | instrumentId ↔ riskFactorId (many-to-many) |
| `risk_metric` | 6 | riskMetricId | partyIdentifier, businessUnitId→GBU, riskIdentifier→risk, riskMeasureId |
| `risk_metric_mr` | 6 | riskMetricId | **config**: confidence 99, horizon 1d, window 10d, methodology Historical Simulation, scenarioSetId, tradeId |
| `risk_metric_mr_obs` | 11 | riskMetricMrObsId | riskMetricId; **observed metricValue** by observationDateTime (MR VaR results) |
| `risk_metric_obs` | 11 | riskMetricObsId | riskMetricId; general VaR obs (mirrors mr_obs) + riskMeasureId, riskIdentifier |
| `risk_measure` | 7 | riskMeasureId | riskIdentifier; VaR / Sensitivity / Stress P&L |
| `risk` | 5 | riskIdentifier | portfolioId, riskTypeId (MKT_IR/PM/FX), businessUnitId |
| `risk_threshold` | 3 | thresholdId | riskMetricId; thresholdValueHigh = warning threshold |
| `risk_threshold_breach` | 3 | breachId | thresholdId, riskMetricObsId |
| `scenario_mr` | 3 | scenarioSetId | SCSET001-003, type Stress |
| `risk_factor_shock` | 15 | (scenarioSetId, riskFactorId) | shockType, shockValue, shockUnit (bps / %) |
| `risk_pnl_record` | 10 | riskPnlRecordId | positionId, bookId, scenarioSetId (**only SCSET001**), riskMetricId; amountBaseCcy |
| `sensitivity` | 10 | sensitivityId | riskMetricId, riskModelId→model; sensitivityValue (USD/bp, USD/%) |
| `model` | 10 | riskModelId | tradeId, bookId, deskId, scenarioSetId; Historical VaR |
| `desk` | 5 | deskId | businessLine, instrumentId |
| `book` | 5 | bookId | bookType Trading, instrumentId |
| `portfolio_hierarchy` | 5 | portfolioId | businessUnitId, deskId, bookId; all parent "Trading" |
| `hsbc_global_Business_Unit` | 4 | businessUnitId | BU001 Rates, BU002 FX, BU003 Commodities, **BU004 Trading (aggregate)** |
| `region_country`, `hsbc_legal_entity`, `hsbc_legal_entity_GBU_location` | 4/3/7 | — | reference/location |

## Verified derived facts (POC snapshot)

- **Latest position.asOfDate = 2026-08-27**; Trading snapshot = 10 positions / 10 trades / 5 instruments / 5 books / 5 desks; net marketValueBcy = 78,960,000.
- **Aggregate Trading VaR** (RMT001, businessUnit BU004 "…- Trading", party PTY_TRADING): current **-38,000,000** @ 2026-08-27 17:00; previous **-37,800,000** @ 2026-08-26; also -37,900,000 @ 08-25; historical breach -108,000,000 @ 2026-06-15.
- **Standalone sub-VaRs** @ 08-27: RMT002 USD Rates -9.2m, RMT003 GBP Rates -7.6m, RMT004 EUR Rates -6.8m, RMT005 XAU -4.4m, RMT006 EUR/USD FX -10.0m — **sum = -38.0m = aggregate** (undiversified stored decomposition).
- **Warning threshold** (THR001→RMT001) = 105,555,556 → **VaR utilisation = 38.0/105.56 = 36.0%** (CALCULATED). Also THR002→RMT002 30m, THR003→RMT006 25m.
- **Model config**: confidence 99%, timeHorizonDays = **1 (only 1-day supported)**, calculationWindowDays = 10, methodology Historical Simulation, distribution Empirical.
- **Stress P&L** (risk_pnl_record, SCSET001 only): total = **-11,100,000**; components USD Rates -2.2m, GBP -3.4m, EUR -1.8m, XAU -1.3m, EUR/USD -2.4m. SCSET002/003 have shocks but **no P&L records** → "Not available from current data model".

## Governance status per metric class
- **STORED**: Current/Previous/sub VaR (risk_metric_mr_obs), Stress P&L (risk_pnl_record), Sensitivity (sensitivity), Warning threshold (risk_threshold), breaches.
- **CALCULATED** (deterministic Python): VaR Change, VaR Utilisation %, historical 1-day risk-factor movements (bps / %), min/max/latest per factor, dimension aggregations at position grain.
- **UNAVAILABLE**: Full independent Historical-Simulation revaluation of positions under each historical shock — workbook has no pricing/revaluation model → "Not independently calculable from current data model". 5-/10-day VaR transformation not stored → horizons other than 1 Day shown unsupported.
