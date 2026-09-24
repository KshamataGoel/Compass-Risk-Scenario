// Types mirror the backend response_models. Kept intentionally permissive where the
// backend returns governed, source-tagged shapes.

export type MetricStatus = "STORED" | "CALCULATED" | "UNAVAILABLE";

export interface Metric {
  metric_name: string;
  value: number | null;
  display?: string | null;
  unit?: string | null;
  status: MetricStatus;
  source: string;
  note?: string | null;
}

export interface Option {
  label: string;
  value: string | number;
  available: boolean;
  reason?: string | null;
  default_selected?: boolean;
  key?: string;
  path?: string;
}

export interface RiskStripeClassification {
  risk_stripe: "MARKET_RISK" | "OPERATIONAL_RESILIENCE";
  confidence: number;
  reason: string;
  extracted_intent: string;
  source: "groq" | "fallback";
}

export interface ORResult {
  risk_stripe: "OPERATIONAL_RESILIENCE";
  available: boolean;
  message?: string;
  candidates?: { scenario_id: string; name: string }[];
  generated_at?: string;
  scenario_resolution?: { scenario_id: string; match_method: string; match_score: number };
  scenario?: Record<string, any>;
  requested_dimensions?: string[];
  event_impact?: Record<string, any>;
  locations?: Record<string, any>[];
  risks?: Record<string, any>[];
  business_services?: Record<string, any>[];
  business_processes?: Record<string, any>[];
  business_units?: Record<string, any>[];
  legal_entities?: Record<string, any>[];
  threshold_breaches?: Record<string, any>;
  controls?: Record<string, any>[];
  issues?: Record<string, any>;
  actions?: Record<string, any>;
  unavailable?: { dimension: string; status: string; reason: string }[];
  lineage?: Record<string, { status: string; source: string }>;
  evidence?: Record<string, any>;
}

export interface ConfigOptions {
  risk_horizons: Option[];
  portfolio_types: Option[];
  lookback_periods: Option[];
  confidence_levels: Option[];
  commentary_dimensions: Option[];
  model_config_summary: Record<string, any>;
}

export interface LineageEntry {
  label: string;
  source: string;
  detail?: string | null;
}

export interface RiskFactor {
  riskFactorId: string;
  riskFactorName: string;
  riskFactorType: string;
  riskFactorSubType: string;
  tenor: string | null;
  currency: string;
  unit: string | null;
  latest_value: number | null;
  historical_min: number | null;
  historical_max: number | null;
  observation_count: number;
  latest_movement: { basis: string; value: number; from: number; to: number; method: string } | null;
  linked_instruments: string[];
}

export interface PnlRow {
  start_date: string;
  end_date: string;
  starting_portfolio_value: number;
  ending_portfolio_value: number;
  historical_pnl: number;
}

export interface TrendPoint {
  as_of_date: string;
  simulation_var: number;
  var_variance: number | null;
  var_variance_pct: number | null;
  trend: string | null;
}

export interface TailPeriod {
  start_date: string;
  end_date: string;
  tail_pnl: number;
}

export interface SimulationBlock {
  available: boolean;
  message?: string;
  portfolio_type?: string;
  lookback_days?: number;
  horizon_days?: number;
  confidence_level?: number;
  tail_probability?: number;
  methodology?: string;
  portfolio_history_full?: { date: string; portfolio_value: number }[];
  portfolio_history_window?: { date: string; portfolio_value: number }[];
  pnl_distribution?: PnlRow[];
  pnl_sorted?: number[];
  simulation_var?: number;
  var_as_of_date?: string;
  tail_quantile?: number;
  tail_period?: TailPeriod | null;
  worst_pnl?: number;
  best_pnl?: number;
  average_pnl?: number;
  observation_count?: number;
  previous_simulation_var?: number | null;
  previous_available?: boolean;
  previous_as_of_date?: string | null;
  var_change?: number | null;
  var_variance?: number | null;
  var_variance_pct?: number | null;
  var_trend_classification?: string | null;
  var_trend?: TrendPoint[];
  trend_threshold_pct?: number;
  unit?: string;
}

export interface ExposureRow {
  exposure: string;
  tail_pnl: number;
  share_pct: number | null;
  classification: string;
}

export interface TailContribution {
  available: boolean;
  message?: string;
  tail_start_date?: string;
  tail_end_date?: string;
  net_tail_pnl?: number;
  positions?: { positionId: string; exposure: string; assetClass: string; starting_value: number; ending_value: number; tail_pnl: number }[];
  by_exposure?: ExposureRow[];
  by_asset_class?: ExposureRow[];
  main_tail_loss_driver?: string | null;
  main_tail_loss_amount?: number | null;
  main_tail_loss_share_pct?: number | null;
  reconciled?: boolean;
}

export interface SimulationResult {
  generated_at: string;
  simulation_parameters: Record<string, any>;
  portfolio: Record<string, any>;
  simulation: SimulationBlock;
  tail_contribution: TailContribution;
  metrics: Metric[];
  var_trend: { observationDateTime: string; metricValue: number }[];
  risk_factors: RiskFactor[];
  historical_movements: Record<string, any>;
  dimension_analysis: Record<string, any>;
  scenario_analysis: Record<string, any>;
  stress_pnl: Record<string, any>;
  sensitivity: any[];
  thresholds: Record<string, any>;
  lineage: Record<string, LineageEntry[]>;
  selected_commentary_dimensions: string[];
  warnings: string[];
}

export interface CommentaryResponse {
  commentary: string;
  generated_at: string;
  model: string;
  evidence: Record<string, any>;
  selected_dimensions: string[];
  source: "groq" | "unavailable" | "error";
}
