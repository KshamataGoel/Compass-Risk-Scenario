"use client";
import React from "react";
import type { ConfigOptions, Option, RiskStripeClassification } from "@/lib/types";
import { Button, Card, Field, Pill } from "./ui";
import { DimensionSelector } from "./DimensionSelector";

export interface SimState {
  portfolio_type: string;
  forward_horizon_days: number;
  lookback_days: number;
  confidence_level: number;
  dimensions: string[];
}

// Ensure the current value is always selectable — the NL parser can resolve a value
// (e.g. 6 observations, 97% confidence) that isn't one of the preset dropdown options.
function withValue(options: Option[], value: string | number, labelFor: (v: string | number) => string): Option[] {
  if (options.some((o) => String(o.value) === String(value))) return options;
  return [...options, { label: labelFor(value), value: value as any, available: true }];
}

function NativeSelect({
  value,
  options,
  onChange,
}: {
  value: string | number;
  options: Option[];
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={String(value)}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-accent/30"
    >
      {options.map((o) => (
        <option key={String(o.value)} value={String(o.value)} disabled={!o.available}>
          {o.label}
          {!o.available ? " — unavailable" : ""}
        </option>
      ))}
    </select>
  );
}

export function SimulationControls({
  config,
  state,
  setState,
  onRun,
  running,
  nlText,
  onNlChange,
  interpretation,
  parseNote,
  parsing,
  classification,
  hideMarketControls,
}: {
  config: ConfigOptions;
  state: SimState;
  setState: (s: SimState) => void;
  onRun: () => void;
  running: boolean;
  nlText: string;
  onNlChange: (v: string) => void;
  interpretation: string | null;
  parseNote: string | null;
  parsing: boolean;
  classification: RiskStripeClassification | null;
  hideMarketControls: boolean;
}) {
  // Manual dropdown controls are hidden — the flow is type a request and Run.
  const showControls = false;
  const stripeLabel = classification
    ? (classification.risk_stripe === "OPERATIONAL_RESILIENCE" ? "Operational Resilience" : "Market Risk")
    : null;
  const horizonUnavailable = config.risk_horizons.find(
    (o) => Number(o.value) === state.forward_horizon_days
  )?.available === false;

  return (
    <Card className="p-5">
      {/* Natural-language input: Groq parses this into the controls below (it never calculates VaR). */}
      <div className="mb-5 rounded-md border border-accent/25 bg-accent/5 p-3">
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Describe your simulation
        </label>
        <textarea
          value={nlText}
          onChange={(e) => onNlChange(e.target.value)}
          rows={2}
          placeholder='e.g. Run Trading VaR for 1 day using the past 6 historical observations at 99% confidence and focus on Asset Class, Business and Scenario.'
          className="w-full resize-y rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent/30"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onRun(); }}
        />
        <p className="mt-1 text-[11px] text-ink-muted">
          Just type your request and click Run — the risk stripe and parameters are detected automatically. (Ctrl/Cmd+Enter to run.)
        </p>
        {interpretation && (
          <p className="mt-2 text-xs text-ink">
            <span className="font-semibold text-accent">Interpreted as:</span> {interpretation}
          </p>
        )}
        {parseNote && (
          <p className="mt-2 rounded border border-warn/30 bg-warn/5 px-2 py-1 text-xs text-warn">{parseNote}</p>
        )}
        {stripeLabel && (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <span className="font-semibold text-ink-muted">Risk Stripe:</span>
            <Pill tone={classification!.risk_stripe === "OPERATIONAL_RESILIENCE" ? "warn" : "accent"}>{stripeLabel}</Pill>
            {classification!.extracted_intent && <span className="text-ink-muted">Intent: {classification!.extracted_intent}</span>}
          </div>
        )}
      </div>

      {hideMarketControls && (
        <p className="mb-2 text-xs text-ink-muted">
          Market-risk controls (horizon, lookback, confidence) do not apply to Operational Resilience and are hidden.
        </p>
      )}

      {!hideMarketControls && showControls && (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Field label="Portfolio Type">
          <NativeSelect
            value={state.portfolio_type}
            options={config.portfolio_types}
            onChange={(v) => setState({ ...state, portfolio_type: v })}
          />
        </Field>
        <Field label="Risk Horizon">
          <NativeSelect
            value={state.forward_horizon_days}
            options={withValue(config.risk_horizons, state.forward_horizon_days, (v) => (Number(v) === 1 ? "1 Day" : `${v} Days`))}
            onChange={(v) => setState({ ...state, forward_horizon_days: Number(v) })}
          />
        </Field>
        <Field label="Historical P&L Lookback">
          <NativeSelect
            value={state.lookback_days}
            options={withValue(config.lookback_periods, state.lookback_days, (v) => (Number(v) === 0 ? "Full history" : `${v} Observations`))}
            onChange={(v) => setState({ ...state, lookback_days: Number(v) })}
          />
          <span className="text-[11px] text-ink-muted">Number of historical P&amp;L observations used in the VaR distribution.</span>
        </Field>
        <Field label="Confidence Level">
          <NativeSelect
            value={state.confidence_level}
            options={withValue(config.confidence_levels, state.confidence_level, (v) => `${v}%`)}
            onChange={(v) => setState({ ...state, confidence_level: Number(v) })}
          />
        </Field>
        <Field label="Management Commentary Dimensions">
          <DimensionSelector
            options={config.commentary_dimensions}
            selected={state.dimensions}
            onChange={(d) => setState({ ...state, dimensions: d })}
          />
        </Field>
      </div>
      )}

      {!hideMarketControls && showControls && horizonUnavailable && (
        <p className="mt-3 text-xs text-warn">
          This horizon needs more trading snapshots than the workbook contains; pick a smaller horizon.
        </p>
      )}

      <div className="mt-5 flex items-center gap-3">
        <Button onClick={onRun} disabled={running || parsing}>
          {parsing ? "Interpreting…" : running ? "Running…" : "Run Scenario Simulation"}
        </Button>
      </div>
    </Card>
  );
}
