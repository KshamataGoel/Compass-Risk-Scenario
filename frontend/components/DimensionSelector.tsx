"use client";
import React, { useState, useRef, useEffect } from "react";
import type { Option } from "@/lib/types";

// Multi-select for commentary dimensions. Only available dimensions can be toggled.
export function DimensionSelector({
  options,
  selected,
  onChange,
}: {
  options: Option[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function toggle(key: string) {
    onChange(selected.includes(key) ? selected.filter((k) => k !== key) : [...selected, key]);
  }

  const availableKeys = options.filter((o) => o.available).map((o) => o.key || String(o.value));
  const allSelected = availableKeys.length > 0 && availableKeys.every((k) => selected.includes(k));

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink hover:bg-slate-50"
      >
        <span className="truncate">
          {selected.length === 0 ? "None selected" : `${selected.length} selected`}
        </span>
        <span className="text-ink-muted">▼</span>
      </button>
      {open && (
        <div className="absolute z-40 mt-1 w-72 rounded-md border border-line bg-panel p-1.5 shadow-lg">
          <div className="flex items-center justify-between px-2 py-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Dimensions</span>
            <button
              className="text-xs font-medium text-accent hover:underline"
              onClick={() => onChange(allSelected ? [] : availableKeys)}
            >
              {allSelected ? "Clear all" : "Select all"}
            </button>
          </div>
          {options.map((o) => {
            const key = o.key || String(o.value);
            const checked = selected.includes(key);
            return (
              <label
                key={key}
                className={`flex items-center gap-2 rounded px-2 py-1.5 text-sm ${
                  o.available ? "cursor-pointer hover:bg-slate-50" : "cursor-not-allowed opacity-50"
                }`}
                title={o.path || ""}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={!o.available}
                  onChange={() => o.available && toggle(key)}
                  className="h-4 w-4 accent-accent"
                />
                <span className="text-ink">{o.label}</span>
                {!o.available && <span className="ml-auto text-[10px] text-warn">n/a</span>}
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
