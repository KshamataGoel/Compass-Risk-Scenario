"use client";
import React from "react";
import { fmtMoney } from "@/lib/format";

// Lightweight, dependency-free SVG charts. They only render values already
// computed by the backend.

export function BarChart({
  data,
  currency = "USD",
  height = 220,
}: {
  data: { label: string; value: number }[];
  currency?: string;
  height?: number;
}) {
  if (!data.length) return <div className="text-sm text-ink-muted">No data.</div>;
  const max = Math.max(...data.map((d) => Math.abs(d.value)), 1);
  const rowH = 30;
  const chartH = Math.max(height, data.length * rowH + 10);
  const labelW = 150;
  const barArea = 360;
  const zeroX = labelW + barArea / 2;

  return (
    <div className="overflow-x-auto scroll-thin">
      <svg width={labelW + barArea + 90} height={chartH} role="img">
        <line x1={zeroX} y1={0} x2={zeroX} y2={chartH} stroke="#e4e8ef" />
        {data.map((d, i) => {
          const y = i * rowH + 6;
          const w = (Math.abs(d.value) / max) * (barArea / 2);
          const neg = d.value < 0;
          const x = neg ? zeroX - w : zeroX;
          return (
            <g key={i}>
              <text x={labelW - 8} y={y + 15} textAnchor="end" fontSize="12" fill="#5b6472">
                {d.label.length > 20 ? d.label.slice(0, 19) + "…" : d.label}
              </text>
              <rect x={x} y={y} width={Math.max(w, 1)} height={18} rx={2} fill={neg ? "#b42318" : "#0f7b57"} opacity={0.85} />
              <text
                x={neg ? x - 6 : x + w + 6}
                y={y + 15}
                textAnchor={neg ? "end" : "start"}
                fontSize="11"
                fill="#0b1220"
                className="tabular"
              >
                {fmtMoney(d.value, currency)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function LineChart({
  points,
  height = 220,
}: {
  points: { x: string; y: number }[];
  height?: number;
}) {
  if (points.length < 1) return <div className="text-sm text-ink-muted">No trend data.</div>;
  const w = 660;
  const padL = 64;
  const padR = 20;
  const padT = 16;
  const padB = 44;
  const ys = points.map((p) => p.y);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const range = maxY - minY || Math.abs(maxY) || 1;
  const innerW = w - padL - padR;
  const innerH = height - padT - padB;
  const stepX = points.length > 1 ? innerW / (points.length - 1) : 0;

  const coords = points.map((p, i) => {
    const x = padL + i * stepX;
    const y = padT + innerH - ((p.y - minY) / range) * innerH;
    return { x, y, label: p.x, value: p.y };
  });
  const path = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");

  return (
    <div className="overflow-x-auto scroll-thin">
      <svg width={w} height={height} role="img">
        {[0, 0.5, 1].map((t) => {
          const y = padT + innerH * t;
          const val = maxY - t * range;
          return (
            <g key={t}>
              <line x1={padL} y1={y} x2={w - padR} y2={y} stroke="#eef1f6" />
              <text x={padL - 8} y={y + 4} textAnchor="end" fontSize="10" fill="#5b6472" className="tabular">
                {fmtMoney(val)}
              </text>
            </g>
          );
        })}
        <path d={path} fill="none" stroke="#0f4c81" strokeWidth={2} />
        {coords.map((c, i) => (
          <g key={i}>
            <circle cx={c.x} cy={c.y} r={3.5} fill="#0f4c81" />
            <text x={c.x} y={c.y - 9} textAnchor="middle" fontSize="9" fill="#0b1220" className="tabular">
              {fmtMoney(c.value)}
            </text>
            <text x={c.x} y={height - 16} textAnchor="middle" fontSize="9" fill="#5b6472">
              {c.label.slice(5, 10)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
