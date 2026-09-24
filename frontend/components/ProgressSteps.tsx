"use client";
import React from "react";
import { Card } from "./ui";

// The nine deterministic processing steps. Step 9 (management summary) is prepared
// deterministically here; Groq is only invoked later from the Management Summary panel.
export const SIM_STEPS = [
  "Loading portfolio",
  "Identifying current positions",
  "Mapping instruments",
  "Mapping risk factors",
  "Loading historical market observations",
  "Calculating historical movements",
  "Retrieving risk metrics",
  "Analysing selected dimensions",
  "Preparing management summary",
];

export function ProgressSteps({ activeStep }: { activeStep: number }) {
  return (
    <Card className="p-5">
      <p className="section-title mb-3">Running deterministic simulation</p>
      <ol className="space-y-2">
        {SIM_STEPS.map((label, i) => {
          const done = i < activeStep;
          const active = i === activeStep;
          return (
            <li key={i} className="flex items-center gap-3 text-sm">
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                  done
                    ? "border-positive bg-positive text-white"
                    : active
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-line text-ink-muted"
                }`}
              >
                {done ? "✓" : i + 1}
              </span>
              <span className={done ? "text-ink-muted line-through" : active ? "font-medium text-ink" : "text-ink-muted"}>
                {label}
              </span>
              {active && <span className="ml-1 animate-pulse text-accent">●</span>}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
