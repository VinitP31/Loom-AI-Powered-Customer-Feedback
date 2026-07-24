/**
 * Shared donut for closed, small-cardinality splits (sentiment, urgency) —
 * share-of-whole reads faster here than a bar, since there's no ranking
 * question (frontend/CLAUDE.md, golden rule 7: self-explanatory). Hovering
 * a slice or its legend row pops that wedge outward, dims the rest, and
 * swaps the center readout to that slice's exact count/share.
 */

import { useState } from "react";
import { tiltHandlers } from "../../utils/motion";

export interface DonutRow {
  name: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  title: string;
  sub: string;
  rows: DonutRow[];
  total: number;
}

const R = 46;
const CIRCUMFERENCE = 2 * Math.PI * R;

export default function DonutChart({ title, sub, rows, total }: DonutChartProps) {
  const [hovered, setHovered] = useState<number | null>(null);

  // Share of the whole donut ring is against processed tickets (`total`),
  // never the sum of the rows themselves — frontend/CLAUDE.md, golden rule
  // 4. The two callers here (sentiment/urgency) always partition all
  // processed tickets, so the ring itself still reads as a full circle.
  let acc = 0;
  const segments = rows.map((row) => {
    const pct = total ? (row.value / total) * 100 : 0;
    const offset = acc;
    acc += pct;
    return { ...row, pct, offset };
  });

  const activeSeg = hovered !== null ? segments[hovered] : null;

  return (
    <div
      className="chart-card rounded-lg border border-hairline bg-surface p-3 transition-[transform,box-shadow] duration-150 will-change-transform hover:shadow-[0_18px_32px_-18px_rgba(0,0,0,0.28)]"
      {...tiltHandlers(3)}
    >
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mb-2 text-xs text-ink-muted">{sub}</p>
      {rows.length === 0 ? (
        <p className="py-6 text-center text-xs text-ink-muted">No data to show.</p>
      ) : (
        <div className="flex items-center gap-4">
          <div className="relative h-[110px] w-[110px] shrink-0">
            <svg viewBox="0 0 110 110" width="110" height="110" className="-rotate-90 overflow-visible">
              <circle cx="55" cy="55" r={R} fill="none" stroke="var(--color-surface-2)" strokeWidth="14" />
              {segments.map((seg, i) => {
                const len = CIRCUMFERENCE * (seg.pct / 100);
                const isHovered = hovered === i;
                const isDimmed = hovered !== null && !isHovered;
                return (
                  <circle
                    key={seg.name}
                    cx="55"
                    cy="55"
                    r={R}
                    fill="none"
                    stroke={seg.color}
                    strokeWidth={isHovered ? 18 : 14}
                    strokeDasharray={`${len} ${CIRCUMFERENCE - len}`}
                    strokeDashoffset={-CIRCUMFERENCE * (seg.offset / 100)}
                    style={{
                      opacity: isDimmed ? 0.35 : 1,
                      filter: isHovered ? `drop-shadow(0 0 5px ${seg.color})` : undefined,
                      transition: "stroke-width 0.15s ease, opacity 0.15s ease, filter 0.15s ease",
                      cursor: "pointer",
                    }}
                    onMouseEnter={() => setHovered(i)}
                    onMouseLeave={() => setHovered(null)}
                  />
                );
              })}
            </svg>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              {activeSeg ? (
                <>
                  <span className="text-lg font-bold" style={{ color: activeSeg.color }}>
                    {activeSeg.value}
                  </span>
                  <span className="text-center text-[9.5px] leading-tight text-ink-muted">
                    {activeSeg.name}
                    <br />
                    {activeSeg.pct.toFixed(1)}%
                  </span>
                </>
              ) : (
                <>
                  <span className="text-lg font-bold text-ink">{total}</span>
                  <span className="text-[9.5px] text-ink-muted">tickets</span>
                </>
              )}
            </div>
          </div>
          <div className="flex flex-1 flex-col gap-0.5">
            {segments.map((seg, i) => (
              <div
                key={seg.name}
                className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors ${hovered === i ? "bg-surface-2" : ""}`}
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
              >
                <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: seg.color }} aria-hidden="true" />
                <span className="flex-1 text-ink-2">{seg.name}</span>
                <span className="font-semibold text-ink">{seg.value}</span>
                <span className="w-11 text-right text-[10.5px] text-ink-muted">{seg.pct.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
