"use client";
import React, { useState } from "react";
import type { CommentaryResponse } from "@/lib/types";
import { Button, Card, Pill, SectionHeader } from "./ui";

export function ManagementSummary({
  onGenerate,
  commentary,
  loading,
  error,
}: {
  onGenerate: () => void;
  commentary: CommentaryResponse | null;
  loading: boolean;
  error: string | null;
}) {
  const [showEvidence, setShowEvidence] = useState(false);

  return (
    <Card className="p-5">
      <SectionHeader
        title="Management Summary"
        subtitle="Generated last, by the LLM, from the deterministic evidence only. The LLM performs no calculations."
        right={
          <Button onClick={onGenerate} disabled={loading}>
            {loading ? "Generating…" : commentary ? "Regenerate Summary" : "Generate Management Summary"}
          </Button>
        }
      />

      {error && <p className="rounded-md border border-negative/30 bg-negative/5 px-3 py-2 text-sm text-negative">{error}</p>}

      {!commentary && !loading && !error && (
        <p className="text-sm text-ink-muted">
          The metrics, historical movements and dimension analysis above are complete and deterministic. Click generate to
          produce the natural-language management commentary.
        </p>
      )}

      {commentary && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {commentary.source === "groq" && <Pill tone="accent">Groq · {commentary.model}</Pill>}
            {commentary.source === "unavailable" && <Pill tone="warn">LLM not configured</Pill>}
            {commentary.source === "error" && <Pill tone="warn">Generation error</Pill>}
            <span className="text-xs text-ink-muted">{new Date(commentary.generated_at).toLocaleString()}</span>
          </div>

          <div className="prose-sm whitespace-pre-wrap rounded-md border border-line bg-slate-50 p-4 text-sm leading-relaxed text-ink">
            {commentary.commentary}
          </div>

          <div>
            <button
              onClick={() => setShowEvidence((v) => !v)}
              className="text-sm font-medium text-accent hover:underline"
            >
              {showEvidence ? "▼ Hide Commentary Evidence" : "▶ View Commentary Evidence"}
            </button>
            {showEvidence && (
              <div className="mt-2">
                <p className="mb-2 text-xs text-ink-muted">
                  These are the exact structured facts supplied to the LLM. No other data was sent, and the raw workbook
                  was never exposed. Dimensions honoured: {commentary.selected_dimensions.join(", ") || "—"}.
                </p>
                <pre className="max-h-96 overflow-auto scroll-thin rounded-md border border-line bg-ink p-3 text-[11px] leading-relaxed text-slate-100">
                  {JSON.stringify(commentary.evidence, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
