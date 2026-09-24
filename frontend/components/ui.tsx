"use client";
import React from "react";
import { statusColor } from "@/lib/format";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function SectionHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-4 mb-3">
      <div>
        <h2 className="text-lg font-semibold text-ink">{title}</h2>
        {subtitle && <p className="text-sm text-ink-muted mt-0.5">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${statusColor(status)}`}>
      {status}
    </span>
  );
}

export function Pill({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "accent" | "warn" }) {
  const tones: Record<string, string> = {
    default: "bg-slate-100 text-ink-muted border-slate-200",
    accent: "bg-accent/10 text-accent border-accent/20",
    warn: "bg-warn/10 text-warn border-warn/20",
  };
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  className = "",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost";
  className?: string;
}) {
  const base = "inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed";
  const styles =
    variant === "primary"
      ? "bg-accent text-white hover:bg-accent/90 shadow-sm"
      : "border border-line bg-panel text-ink hover:bg-slate-50";
  return (
    <button className={`${base} ${styles} ${className}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</span>
      {children}
    </label>
  );
}

export function EmptyNote({ children }: { children: React.ReactNode }) {
  return <div className="rounded-md border border-dashed border-warn/40 bg-warn/5 px-3 py-2 text-sm text-warn">{children}</div>;
}

export function InfoDot({ onClick, active }: { onClick: () => void; active?: boolean }) {
  return (
    <button
      onClick={onClick}
      title="View data lineage"
      className={`ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border text-[10px] font-bold ${
        active ? "border-accent bg-accent text-white" : "border-ink-muted/40 text-ink-muted hover:border-accent hover:text-accent"
      }`}
    >
      i
    </button>
  );
}
