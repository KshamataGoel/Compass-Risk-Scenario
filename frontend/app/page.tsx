"use client";
import React, { useEffect, useState } from "react";
import { api } from "@/services/api";
import type { CommentaryResponse, ConfigOptions, LineageEntry, SimulationResult } from "@/lib/types";
import { SimulationControls, type SimState } from "@/components/SimulationControls";
import { ProgressSteps, SIM_STEPS } from "@/components/ProgressSteps";
import { SimulationParameters } from "@/components/SimulationParameters";
import { PortfolioOverview } from "@/components/PortfolioOverview";
import { MetricCards } from "@/components/MetricCards";
import { HistoricalPnl } from "@/components/HistoricalPnl";
import { TailContribution } from "@/components/TailContribution";
import { SimVarTrend } from "@/components/SimVarTrend";
import { RiskFactorTable } from "@/components/RiskFactorTable";
import { HistoricalMovements } from "@/components/HistoricalMovements";
import { DimensionAnalysis } from "@/components/DimensionAnalysis";
import { ScenarioAnalysis } from "@/components/ScenarioAnalysis";
import { SensitivityTable } from "@/components/SensitivityTable";
import { ManagementSummary } from "@/components/ManagementSummary";
import { SaveSimulation, type SaveState } from "@/components/SaveSimulation";
import { OperationalResiliencePanel } from "@/components/OperationalResiliencePanel";
import { DataLineageDrawer } from "@/components/DataLineage";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Card } from "@/components/ui";
import type { RiskStripeClassification, ORResult } from "@/lib/types";

export default function Page() {
  const [config, setConfig] = useState<ConfigOptions | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [state, setState] = useState<SimState>({
    portfolio_type: "Trading",
    forward_horizon_days: 1,
    lookback_days: 10,
    confidence_level: 99,
    dimensions: [],
  });

  const [running, setRunning] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const [commentary, setCommentary] = useState<CommentaryResponse | null>(null);
  const [commentaryLoading, setCommentaryLoading] = useState(false);
  const [commentaryError, setCommentaryError] = useState<string | null>(null);

  const [lineage, setLineage] = useState<{ title: string; entries: LineageEntry[] } | null>(null);

  const [saveState, setSaveState] = useState<SaveState | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Natural-language input (parsing state kept separate from simulation state so manual
  // dropdown overrides are not overwritten unless the sentence itself changes).
  const [nlText, setNlText] = useState("");
  const [lastParsedText, setLastParsedText] = useState<string | null>(null);
  const [interpretation, setInterpretation] = useState<string | null>(null);
  const [parseNote, setParseNote] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);

  // Risk-stripe routing (Market Risk vs Operational Resilience).
  const [classification, setClassification] = useState<RiskStripeClassification | null>(null);
  const [routing, setRouting] = useState(false);
  const [orResult, setOrResult] = useState<ORResult | null>(null);
  const [orCommentary, setOrCommentary] = useState<CommentaryResponse | null>(null);
  const [orCommentaryLoading, setOrCommentaryLoading] = useState(false);
  const stripe = classification?.risk_stripe ?? null;

  // Load config options (all derived from the workbook) and default-select dimensions.
  useEffect(() => {
    api
      .configOptions()
      .then((cfg) => {
        setConfig(cfg);
        const defaults = cfg.commentary_dimensions.filter((d) => d.available).map((d) => d.key || String(d.value));
        // Default lookback: prefer 5 observations (a readable VaR trend + previous VaR); else the largest available.
        const availableLookbacks = cfg.lookback_periods.filter((l) => l.available).map((l) => Number(l.value));
        const defaultLookback = availableLookbacks.includes(5)
          ? 5
          : availableLookbacks.length
          ? Math.max(...availableLookbacks)
          : 5;
        setState((s) => ({
          ...s,
          dimensions: defaults,
          forward_horizon_days: Number(cfg.risk_horizons.find((h) => h.available)?.value ?? 1),
          lookback_days: defaultLookback,
          confidence_level: Number(cfg.confidence_levels?.find((c) => Number(c.value) === 99)?.value ?? cfg.confidence_levels?.[cfg.confidence_levels.length - 1]?.value ?? 99),
          portfolio_type: String(cfg.portfolio_types.find((p) => p.available)?.value ?? "Trading"),
        }));
      })
      .catch((e) => setConfigError(String(e)));
  }, []);

  // Primary action: classify the risk stripe first, then run the matching engine.
  async function handleRun() {
    // Route only when there's a natural-language request; empty box = Market Risk (controls as set).
    if (nlText.trim()) {
      setRouting(true);
      try {
        const c = await api.route(nlText);
        setClassification(c);
        if (c.risk_stripe === "OPERATIONAL_RESILIENCE") {
          await runOperationalResilience();
          return;
        }
      } catch {
        // Routing failed — fall back to the existing Market Risk path.
        setClassification({ risk_stripe: "MARKET_RISK", confidence: 0, reason: "Router unavailable; defaulted to Market Risk.", extracted_intent: "", source: "fallback" });
      } finally {
        setRouting(false);
      }
    } else {
      setClassification({ risk_stripe: "MARKET_RISK", confidence: 1, reason: "No request text; using the displayed controls.", extracted_intent: "Market risk VaR", source: "fallback" });
    }

    await runMarketRisk();
  }

  async function runOperationalResilience() {
    setRunning(true);
    setRunError(null);
    setResult(null);              // clear any Market Risk result
    setOrResult(null);
    setOrCommentary(null);
    try {
      const r = await api.operationalResilience(nlText);
      setOrResult(r);
    } catch (e) {
      setRunError(String(e));
    } finally {
      setRunning(false);
      setRouting(false);
    }
  }

  async function generateOrCommentary() {
    if (!orResult) return;
    setOrCommentaryLoading(true);
    try {
      setOrCommentary(await api.orCommentary(orResult));
    } catch (e) {
      setOrCommentary({ commentary: String(e), generated_at: "", model: "", evidence: {}, selected_dimensions: [], source: "error" } as any);
    } finally {
      setOrCommentaryLoading(false);
    }
  }

  // Market Risk path: interpret the sentence (if new) into the controls, then run.
  async function runMarketRisk() {
    setOrResult(null);           // clear any Operational Resilience result
    let params: SimState = state;

    if (nlText.trim() && nlText !== lastParsedText) {
      setParsing(true);
      setParseNote(null);
      try {
        const res = await api.parseParameters(nlText, state as unknown as Record<string, any>);
        const r = res.resolved;
        params = {
          portfolio_type: r.portfolio_type,
          forward_horizon_days: r.risk_horizon_days,
          lookback_days: r.historical_pnl_lookback,
          confidence_level: r.confidence_level,
          dimensions: r.commentary_dimensions,
        };
        setState(params);                       // populate the visible dropdowns
        setInterpretation(res.interpretation);
        setParseNote(res.note);                 // non-blocking note if Groq was unavailable
        setLastParsedText(nlText);
      } catch (e) {
        // Never block the simulation — fall back to the displayed controls.
        setParseNote("Could not interpret the natural-language request. Running with the displayed simulation parameters.");
        params = state;
      } finally {
        setParsing(false);
      }
    }

    await runSimulation(params);
  }

  async function runSimulation(params: SimState = state) {
    setRunning(true);
    setRunError(null);
    setResult(null);
    setCommentary(null);
    setCommentaryError(null);
    setSaveState(null);
    setSaveError(null);
    setActiveStep(0);

    // Animate the deterministic steps while the backend computes.
    const timer = setInterval(() => {
      setActiveStep((s) => (s < SIM_STEPS.length - 1 ? s + 1 : s));
    }, 260);

    try {
      const res = await api.runSimulation(params);
      // Let the step animation reach the end for a coherent UX.
      await new Promise((r) => setTimeout(r, 300));
      clearInterval(timer);
      setActiveStep(SIM_STEPS.length);
      setResult(res);
    } catch (e) {
      clearInterval(timer);
      setRunError(String(e));
    } finally {
      setRunning(false);
    }
  }

  async function generateCommentary() {
    if (!result) return;
    setCommentaryLoading(true);
    setCommentaryError(null);
    try {
      const c = await api.commentary(result);
      setCommentary(c);
    } catch (e) {
      setCommentaryError(String(e));
    } finally {
      setCommentaryLoading(false);
    }
  }

  async function saveSimulation() {
    if (!result) return;
    setSaving(true);
    setSaveError(null);
    try {
      const s = await api.saveSimulation(result);
      setSaveState(s);
    } catch (e) {
      setSaveError(String(e));
    } finally {
      setSaving(false);
    }
  }

  function openLineage(key: string) {
    if (!result) return;
    const entries = result.lineage[key];
    if (entries) setLineage({ title: key, entries });
  }

  const portfolioAvailable = result?.portfolio?.available;

  return (
    <div className="min-h-screen">
      {/* Genpact-style header bar */}
      <header className="border-b-2 border-accent bg-ink">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
          <span className="font-display text-base font-semibold lowercase tracking-tight text-slate-400">genpact</span>
          <div className="h-8 w-px bg-white/15" />
          <div className="leading-none">
            <div className="font-display text-2xl font-extrabold tracking-tight text-white">Risk Scenario Simulation</div>
            <div className="mt-1 text-[10px] font-bold uppercase tracking-[0.18em] text-accent">
              Market Risk &amp; Operational Resilience
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
      {configError && (
        <Card className="mb-4 p-4">
          <p className="text-sm text-negative">
            Could not load configuration from the backend: {configError}. Ensure the FastAPI backend is running on port 8000.
          </p>
        </Card>
      )}

      {config && (
        <SimulationControls
          config={config}
          state={state}
          setState={setState}
          onRun={handleRun}
          running={running || routing}
          nlText={nlText}
          onNlChange={setNlText}
          interpretation={stripe === "OPERATIONAL_RESILIENCE" ? null : interpretation}
          parseNote={parseNote}
          parsing={parsing}
          classification={classification}
          hideMarketControls={stripe === "OPERATIONAL_RESILIENCE"}
        />
      )}

      {running && (
        <div className="mt-4">
          <ProgressSteps activeStep={activeStep} />
        </div>
      )}

      {runError && (
        <Card className="mt-4 p-4">
          <p className="text-sm text-negative">Simulation failed: {runError}</p>
        </Card>
      )}

      {/* Operational Resilience risk-stripe path */}
      {orResult && !running && (
        <div className="mt-6">
          <OperationalResiliencePanel
            data={orResult}
            commentary={orCommentary}
            commentaryLoading={orCommentaryLoading}
            onGenerate={generateOrCommentary}
          />
        </div>
      )}

      {/* Market Risk risk-stripe path (unchanged) */}
      {result && !running && (
        <ErrorBoundary>
        <div className="mt-6 space-y-6">
          {result.warnings?.length > 0 && (
            <div className="rounded-md border border-warn/30 bg-warn/5 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-warn">Governance notes</p>
              <ul className="mt-1 list-disc pl-5 text-sm text-warn">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <SimulationParameters params={result.simulation_parameters} />
          <PortfolioOverview portfolio={result.portfolio} onLineage={() => openLineage("Portfolio")} />

          {portfolioAvailable && (
            <>
              <MetricCards metrics={result.metrics} onLineage={openLineage} />
              <HistoricalPnl
                simulation={result.simulation}
                utilisation={result.thresholds?.utilisation || {}}
                onLineage={() => openLineage("Simulation VaR")}
              />
              {result.simulation?.available && (
                <TailContribution tail={result.tail_contribution} unit={result.simulation?.unit || "USD"} />
              )}
              {result.simulation?.available && <SimVarTrend simulation={result.simulation} />}
              {result.simulation?.available && (
                <SaveSimulation onSave={saveSimulation} saving={saving} result={saveState} error={saveError} />
              )}
              <RiskFactorTable riskFactors={result.risk_factors} onLineage={() => openLineage("Associated Risk Factors")} />
              <HistoricalMovements historical={result.historical_movements} />
              <DimensionAnalysis
                dimensions={result.selected_commentary_dimensions}
                analysis={result.dimension_analysis}
                stressPnl={result.stress_pnl}
                onLineage={openLineage}
              />
              {!result.selected_commentary_dimensions.includes("Scenario") && (
                <ScenarioAnalysis scenarioAnalysis={result.scenario_analysis} stressPnl={result.stress_pnl} />
              )}
              <SensitivityTable sensitivity={result.sensitivity} onLineage={() => openLineage("Sensitivity")} />
              <ManagementSummary
                onGenerate={generateCommentary}
                commentary={commentary}
                loading={commentaryLoading}
                error={commentaryError}
              />
            </>
          )}
        </div>
        </ErrorBoundary>
      )}

      <footer className="mt-10 border-t border-line pt-4 text-center text-xs text-ink-muted">
        Source of truth: Market Risk workbook. Every value is STORED, CALCULATED from workbook data, or explicitly marked
        unavailable.
      </footer>

      <DataLineageDrawer
        title={lineage?.title || null}
        entries={lineage?.entries || null}
        onClose={() => setLineage(null)}
      />
      </main>
    </div>
  );
}
