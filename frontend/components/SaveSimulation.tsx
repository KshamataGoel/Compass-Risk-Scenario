"use client";
import React from "react";
import { Button, Card, Pill, SectionHeader } from "./ui";

export interface SaveState {
  saved: boolean;
  run_id?: string;
  saved_at?: string;
  path?: string;
  simulation_var?: number;
  runs_in_file?: number;
  message?: string;
}

// Save is an explicit, post-validation action (spec §20-21). It persists the
// Python-calculated Simulation VaR to the output workbook — never the stored source VaR.
export function SaveSimulation({
  onSave,
  saving,
  result,
  error,
}: {
  onSave: () => void;
  saving: boolean;
  result: SaveState | null;
  error: string | null;
}) {
  return (
    <Card className="p-5">
      <SectionHeader
        title="Save Simulation"
        subtitle="Run only calculates. Save persists the calculated Simulation VaR to Market_Risk_Simulation_Output.xlsx — the source workbook is never modified."
        right={
          <Button onClick={onSave} disabled={saving} variant="ghost">
            {saving ? "Saving…" : "Save Simulation"}
          </Button>
        }
      />
      {error && (
        <p className="rounded-md border border-negative/30 bg-negative/5 px-3 py-2 text-sm text-negative">{error}</p>
      )}
      {result?.saved && (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Pill tone="accent">Saved</Pill>
          <span className="text-ink-muted">Run</span>
          <code className="rounded bg-slate-50 px-2 py-0.5 text-xs text-accent">{result.run_id}</code>
          <span className="text-ink-muted">·</span>
          <span className="text-ink-muted">{result.runs_in_file} run(s) in file</span>
          <span className="text-ink-muted">·</span>
          <code className="truncate text-xs text-ink-muted" title={result.path}>{result.path}</code>
        </div>
      )}
      {result && !result.saved && (
        <p className="rounded-md border border-warn/30 bg-warn/5 px-3 py-2 text-sm text-warn">{result.message}</p>
      )}
    </Card>
  );
}
