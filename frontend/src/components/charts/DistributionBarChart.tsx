/**
 * Shared horizontal bar chart for every distribution view (category,
 * theme, sentiment, urgency). One hue per row, sorted descending by
 * count, with a count + %-of-processed tooltip and a visible axis label
 * so every chart is self-explanatory without a walkthrough
 * (frontend/CLAUDE.md, golden rule 7). Percent is always computed
 * against `total` (the caller passes `processed`), never total_rows.
 */

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { tiltHandlers } from "../../utils/motion";

export interface DistributionRow {
  name: string;
  value: number;
  color: string;
  /** Set when this row is one of several tied for the top spot
   * (analytics.category_leaders / theme_leaders) — rendered as a small tag. */
  tied?: boolean;
}

interface DistributionBarChartProps {
  title: string;
  sub: string;
  rows: DistributionRow[];
  total: number;
  /** When set, bars become clickable: clicking a bar calls this with its
   * name (clicking the already-active bar clears the filter by passing
   * null), and the active bar gets a visible ring so the filter state is
   * legible without checking the table below. */
  activeName?: string | null;
  onBarClick?: (name: string | null) => void;
}

function ChartTooltip({
  active,
  payload,
  total,
}: {
  active?: boolean;
  payload?: { payload: DistributionRow }[];
  total: number;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const pct = total ? ((row.value / total) * 100).toFixed(1) : "0.0";
  return (
    <div className="flex items-center gap-2 rounded-md border border-hairline bg-ink px-3 py-2 text-xs text-background shadow-lg">
      <span className="h-2 w-2 shrink-0 rounded-sm" style={{ background: row.color }} aria-hidden="true" />
      <div>
        <p className="font-semibold">{row.name}</p>
        <p>
          {row.value} tickets · {pct}%
        </p>
      </div>
    </div>
  );
}

/** The count label to the right of each bar; the unique leader (strictly
 * more than every other row — never on a tie) gets a small crown appended.
 * A tie intentionally gets no crown — frontend/CLAUDE.md's null-leader
 * handling already says never imply a single winner exists when one
 * doesn't, so this only fires when there truly is one. */
function CountLabel({
  x,
  y,
  width,
  value,
  isLeader,
}: {
  x?: number | string;
  y?: number | string;
  width?: number | string;
  value?: number | string | null;
  isLeader: boolean;
}) {
  return (
    <text x={Number(x ?? 0) + Number(width ?? 0) + 4} y={Number(y ?? 0) + 9} fontSize={11} fill="var(--color-ink-2)">
      {value}
      {isLeader && <tspan fontSize={10}> &#128081;</tspan>}
    </text>
  );
}

export default function DistributionBarChart({
  title,
  sub,
  rows,
  total,
  activeName,
  onBarClick,
}: DistributionBarChartProps) {
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  const height = Math.max(sorted.length * 23, 64);
  const clickable = Boolean(onBarClick);
  const leaderName = sorted.length > 0 && (sorted.length === 1 || sorted[0].value > sorted[1].value) ? sorted[0].name : null;

  return (
    <div
      className="chart-card rounded-lg border border-hairline bg-surface p-3 transition-[transform,box-shadow] duration-150 will-change-transform hover:shadow-[0_18px_32px_-18px_rgba(0,0,0,0.28)]"
      {...tiltHandlers(3)}
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {clickable && <span className="text-[10px] text-ink-muted">click a bar to filter the table</span>}
      </div>
      <p className="mb-2 text-xs text-ink-muted">{sub}</p>
      {sorted.length === 0 ? (
        <p className="py-6 text-center text-xs text-ink-muted">No data to show.</p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={sorted} layout="vertical" margin={{ left: 4, right: 28, top: 0, bottom: 0 }}>
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="name"
              width={150}
              tick={{ fontSize: 11, fill: "var(--color-ink-2)" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<ChartTooltip total={total} />} cursor={{ fill: "var(--color-surface-2)" }} />
            <Bar
              dataKey="value"
              radius={[0, 4, 4, 0]}
              maxBarSize={16}
              isAnimationActive={false}
              cursor={clickable ? "pointer" : undefined}
              onClick={
                onBarClick
                  ? (row: unknown) => {
                      const name = (row as DistributionRow).name;
                      onBarClick(activeName === name ? null : name);
                    }
                  : undefined
              }
            >
              {sorted.map((row) => {
                const isLeader = leaderName === row.name;
                return (
                  <Cell
                    key={row.name}
                    className="dist-bar-cell"
                    fill={row.color}
                    fillOpacity={activeName && activeName !== row.name ? 0.35 : 1}
                    stroke={activeName === row.name ? "var(--color-accent)" : undefined}
                    strokeWidth={activeName === row.name ? 2 : 0}
                    style={{
                      filter: isLeader ? `drop-shadow(0 0 3px ${row.color})` : undefined,
                      cursor: clickable ? "pointer" : undefined,
                    }}
                  />
                );
              })}
              <LabelList
                dataKey="value"
                position="right"
                content={(props: unknown) => {
                  const p = props as { index?: number; x?: number | string; y?: number | string; width?: number | string; value?: number | string };
                  const index = p.index ?? -1;
                  const isLeader = index >= 0 && sorted[index]?.name === leaderName;
                  return <CountLabel x={p.x} y={p.y} width={p.width} value={p.value} isLeader={isLeader} />;
                }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
