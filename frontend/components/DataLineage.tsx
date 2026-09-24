"use client";
import React from "react";
import type { LineageEntry } from "@/lib/types";

// Slide-over drawer showing the workbook lineage for a metric family.
export function DataLineageDrawer({
  title,
  entries,
  onClose,
}: {
  title: string | null;
  entries: LineageEntry[] | null;
  onClose: () => void;
}) {
  if (!title || !entries) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative h-full w-full max-w-md overflow-y-auto bg-panel shadow-xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-line bg-panel px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Data Lineage</p>
            <h3 className="text-base font-semibold text-ink">{title}</h3>
          </div>
          <button onClick={onClose} className="rounded p-1 text-ink-muted hover:bg-slate-100" aria-label="Close">✕</button>
        </div>
        <div className="space-y-3 p-5">
          <p className="text-sm text-ink-muted">
            Every figure traces to the approved Market Risk workbook. Sources for this metric:
          </p>
          {entries.map((e, i) => (
            <div key={i} className="rounded-md border border-line p-3">
              <p className="text-sm font-semibold text-ink">{e.label}</p>
              <code className="mt-1 block break-words rounded bg-slate-50 px-2 py-1 text-xs text-accent">{e.source}</code>
              {e.detail && <p className="mt-1.5 text-xs text-ink-muted">{e.detail}</p>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
