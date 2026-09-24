"use client";
import React, { useState } from "react";
import type { CommentaryResponse, ORResult } from "@/lib/types";
import { Button, Card, EmptyNote, Pill, SectionHeader } from "./ui";
import { fmtMoney, fmtNumber } from "@/lib/format";

// Operational Resilience risk-stripe layout. Every figure is deterministic (from the OR
// workbook); the LLM only writes the short management summary from the evidence.
export function OperationalResiliencePanel({
  data,
  commentary,
  commentaryLoading,
  onGenerate,
}: {
  data: ORResult;
  commentary: CommentaryResponse | null;
  commentaryLoading: boolean;
  onGenerate: () => void;
}) {
  const [showEvidence, setShowEvidence] = useState(false);

  if (!data.available) {
    return (
      <Card className="p-5">
        <SectionHeader title="Operational Resilience" />
        <EmptyNote>{data.message || "Could not resolve a scenario."}</EmptyNote>
        {data.candidates && data.candidates.length > 0 && (
          <div className="mt-2 text-sm text-ink-muted">
            Available scenarios: {data.candidates.map((c) => `${c.scenario_id} (${c.name})`).join(", ")}
          </div>
        )}
      </Card>
    );
  }

  const s = data.scenario || {};
  const ei = data.event_impact || {};
  const tb = data.threshold_breaches || {};
  const kpis = [
    { label: "Related Events", value: fmtNumber(ei.event_count) },
    { label: "Duration (hrs)", value: ei.duration_hours != null ? fmtNumber(ei.duration_hours) : "—" },
    { label: "Financial Impact", value: ei.total_financial_impact != null ? fmtMoney(ei.total_financial_impact, ei.currency || "USD") : "—" },
    { label: "Locations", value: fmtNumber((data.locations || []).length) },
    { label: "Risks", value: fmtNumber((data.risks || []).length) },
    { label: "Breaches", value: fmtNumber(tb.breach_count ?? 0) },
  ];

  return (
    <div className="space-y-6">
      {/* Scenario */}
      <Card className="p-5">
        <SectionHeader title="Scenario" subtitle={`${data.scenario_resolution?.scenario_id ?? ""} · resolved by ${data.scenario_resolution?.match_method ?? "match"}`} />
        <div className="text-lg font-semibold text-ink">{s.scenarioName}</div>
        <p className="mt-1 text-sm text-ink-muted">{s.scenarioDescription}</p>
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-ink-muted">
          <Pill tone="accent">Impact: {s.scenarioImpact}</Pill>
          <Pill tone="default">Breakdown: {s.impactBreakdown}</Pill>
          <Pill tone="default">Anchor event: {s.anchor_event}</Pill>
        </div>
      </Card>

      {/* Impact overview */}
      <Card className="p-5">
        <SectionHeader title="Impact Overview" subtitle={`${ei.period_start ?? ""} → ${ei.period_end ?? ""}`} />
        <div className="flex flex-wrap gap-3">
          {kpis.map((k) => (
            <div key={k.label} className="rounded-md border border-line bg-slate-50 px-3 py-2">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-ink-muted">{k.label}</div>
              <div className="text-sm font-semibold tabular text-ink">{k.value}</div>
            </div>
          ))}
        </div>
        {ei.likelihood_breakdown && Object.keys(ei.likelihood_breakdown).length > 0 && (
          <p className="mt-3 text-xs text-ink-muted">Likelihood: {Object.entries(ei.likelihood_breakdown).map(([k, v]) => `${k} ${v}`).join(", ")}</p>
        )}
      </Card>

      {/* Unavailable notices */}
      {data.unavailable && data.unavailable.length > 0 && (
        <Card className="p-5">
          <SectionHeader title="Requested but Unavailable" subtitle="Not represented in the Operational Resilience data model — not fabricated." />
          <div className="space-y-2">
            {data.unavailable.map((u, i) => (
              <div key={i} className="rounded-md border border-warn/30 bg-warn/5 px-3 py-2 text-sm text-warn">
                <span className="font-semibold">{u.dimension}</span> — {u.status}: {u.reason}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Two-column detail tables */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SimpleTable title="Impacted Locations" rows={data.locations || []}
          cols={[["locationName", "Location"], ["countryName", "Country"], ["regionCode", "Region"], ["event_count", "Events"]]} />
        <SimpleTable title="Impacted Business Services" rows={data.business_services || []}
          cols={[["serviceName", "Service"], ["serviceTier", "Tier"], ["serviceHours", "Hours"]]} />
        <SimpleTable title="Impacted Business Processes" rows={data.business_processes || []}
          cols={[["businessProcessName", "Process"]]} />
        <SimpleTable title="Risk Impact" rows={data.risks || []}
          cols={[["riskStatement", "Risk"], ["impactRating", "Rating"], ["riskType", "Type"]]} />
      </div>

      {/* Threshold / breach */}
      <Card className="p-5">
        <SectionHeader title="Threshold / Breach Analysis"
          subtitle={tb.available ? `${tb.breach_count} breach(es), ${tb.open_breach_count} open` : "No breach data"} />
        {tb.available && (tb.breaches || []).length > 0 ? (
          <Table cols={[["breachId", "Breach"], ["riskIdentifier", "Risk"], ["observedValue", "Observed"], ["breachSeverity", "Severity"], ["breachStatusCode", "Status"]]} rows={tb.breaches} />
        ) : (
          <EmptyNote>No threshold breaches for this scenario's risks.</EmptyNote>
        )}
      </Card>

      {/* Controls / issues / actions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <SimpleTable title="Controls" rows={data.controls || []}
          cols={[["controlDescription", "Control"], ["controlRating", "Rating"]]} />
        <SimpleTable title={`Issues (${data.issues?.open ?? 0} open / ${data.issues?.total ?? 0})`} rows={data.issues?.issues || []}
          cols={[["issueDescription", "Issue"], ["severityCode", "Sev"], ["statusCode", "Status"]]} />
        <SimpleTable title={`Actions (${data.actions?.open ?? 0} open / ${data.actions?.total ?? 0})`} rows={data.actions?.actions || []}
          cols={[["description", "Action"], ["statusCode", "Status"], ["targetDate", "Target"]]} />
      </div>

      {/* Business units / legal entities */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SimpleTable title="Impacted Business Units" rows={data.business_units || []}
          cols={[["businessUnitId", "Unit"], ["businessUnitName", "Name"]]} />
        <SimpleTable title="Impacted Legal Entities" rows={data.legal_entities || []}
          cols={[["hsbcLegalEntityCode", "Legal Entity"], ["locationId", "Location"]]} />
      </div>

      {/* Management summary */}
      <Card className="p-5">
        <SectionHeader title="Management Summary" subtitle="Short summary generated by the LLM from the deterministic evidence only."
          right={<Button onClick={onGenerate} disabled={commentaryLoading} variant="ghost">{commentaryLoading ? "Generating…" : commentary ? "Regenerate" : "Generate Management Summary"}</Button>} />
        {commentary ? (
          <>
            <div className="mb-2 flex items-center gap-2 text-xs">
              <Pill tone={commentary.source === "groq" ? "accent" : "warn"}>{commentary.source === "groq" ? `Groq · ${commentary.model}` : "LLM not configured"}</Pill>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{commentary.commentary}</p>
          </>
        ) : (
          <EmptyNote>Deterministic facts are shown above. Click Generate for the concise summary.</EmptyNote>
        )}
        <button onClick={() => setShowEvidence((v) => !v)} className="mt-3 text-sm font-medium text-accent hover:underline">
          {showEvidence ? "▼ Hide Commentary Evidence" : "▶ View Commentary Evidence"}
        </button>
        {showEvidence && (
          <pre className="mt-2 max-h-80 overflow-auto rounded-md border border-line bg-slate-50 p-3 text-[11px] text-ink-muted">
            {JSON.stringify(data.evidence, null, 2)}
          </pre>
        )}
      </Card>
    </div>
  );
}

function SimpleTable({ title, rows, cols }: { title: string; rows: any[]; cols: [string, string][] }) {
  return (
    <Card className="p-5">
      <SectionHeader title={title} />
      {rows && rows.length > 0 ? <Table cols={cols} rows={rows} /> : <EmptyNote>None for this scenario.</EmptyNote>}
    </Card>
  );
}

function Table({ cols, rows }: { cols: [string, string][]; rows: any[] }) {
  return (
    <div className="overflow-x-auto scroll-thin">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-muted">
            {cols.map(([k, label]) => <th key={k} className="py-2 pr-4 font-semibold">{label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-line/60">
              {cols.map(([k]) => <td key={k} className="py-1.5 pr-4 text-ink">{r[k] == null ? "—" : String(r[k])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
