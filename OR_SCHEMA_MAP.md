# Operational Resilience Workbook — Internal Schema Map

Source: `Database/Operational_Resilience_POC_Database.xlsx` — 20 sheets (incl. README).
**Separate model from Market Risk** — similarly named entities are NOT the same business meaning.
Column headers carry a literal ` (FK)` suffix (stripped on load, same as MR).

## Scenario → event grouping (the key relationship)
`scenario.eventIdentifier` is the scenario's **anchor/starting event**. Events are partitioned by
ordering `eventIdentifier` and assigning each event to the scenario whose anchor is the greatest
anchor ≤ that event (i.e. contiguous ranges up to the next scenario's anchor):
- **SCN001** Asian Storm → EVT001–004 (4 events; RSK001, RSK002) — financial impact 620,000 ✓
- **SCN002** Technology → EVT005–007 (3 events; RSK003, RSK004)
- **SCN003** Third-Party → EVT008–010 (3 events; RSK005, RSK006)

## Join paths (workbook-derived only)
| From | To | Via |
|---|---|---|
| scenario | events | anchor range on eventIdentifier |
| risk_event | risk | riskIdentifier |
| risk_event | region_country | locationId |
| risk_event | issue | issueId |
| risk_event | risk_threshold | thresholdId |
| risk | risk_type | riskTypeId |
| risk | business_service | businessServiceId |
| risk | business_process | businessProcessId |
| risk | hsbc_global_Business_Unit | businessUnitId |
| risk | region_country | locationId |
| location | hsbc_legal_entity | hsbc_legal_entity_GBU_location.locationId → hsbcLegalEntityPartyId |
| risk | risk_measure → risk_metric → risk_metric_obs | riskIdentifier |
| risk_metric_obs | risk_threshold_breach | riskMetricObsId |
| risk_metric | risk_threshold | riskMetricId |
| risk | control / issue / risk_assessment | riskIdentifier |
| issue | action | issueId |

## Deterministic calculations (Python)
- **Event impact**: COUNT(events), MIN(start)/MAX(end), duration hours, SUM(financialImpactAmount), likelihood mix, statuses, nonFinancialImpactType set.
- **Locations**: DISTINCT event.locationId → region_country (name/country/region), per-location event count.
- **Risks**: DISTINCT event.riskIdentifier → risk (statement, impactRating) + risk_type (riskType, classification).
- **Business services / processes**: risk.businessServiceId → business_service (name, tier, hours); risk.businessProcessId → business_process (name).
- **Business units / legal entities**: risk.businessUnitId → hsbc_global_Business_Unit; location → hsbc_legal_entity_GBU_location → hsbc_legal_entity.
- **Threshold/breach**: scenario risks → risk_metric_obs → risk_threshold_breach (count, severity, status, observedValue) + risk_threshold.
- **Controls/issues/actions**: control.riskIdentifier; event.issueId → issue (severity, status, open count); action.issueId → action (status, targetDate). control rating from risk_assessment.controlRating.

## UNAVAILABLE by design (README-confirmed)
Industry/sector, vendor/third-party inventory, people inventory, physical-site inventory are NOT in the LDM → return `{"status":"UNAVAILABLE","reason":"…not represented in the current Operational Resilience data model."}` — never invent.
