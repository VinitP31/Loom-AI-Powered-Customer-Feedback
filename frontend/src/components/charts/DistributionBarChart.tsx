/**
 * Shared horizontal bar chart for every distribution view (category,
 * theme, sentiment, urgency). One hue per row, sorted descending by
 * count, with a count + %-of-processed tooltip and a visible axis label
 * so every chart is self-explanatory without a walkthrough
 * (frontend/CLAUDE.md, golden rule 7). Percent is always computed
 * against `total` (the caller passes `processed`), never total_rows.
 */

import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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
    <div className="rounded-md border border-hairline bg-ink px-3 py-2 text-xs text-background shadow-lg">
      <p className="font-semibold">{row.name}</p>
      <p>
        {row.value} tickets · {pct}%
      </p>
    </div>
  );
}

export default function DistributionBarChart({ title, sub, rows, total }: DistributionBarChartProps) {
  const sorted = [...rows].sort((a, b) => b.value - a.value);
  const height = Math.max(sorted.length * 32, 80);

  return (
    <div className="rounded-lg border border-hairline bg-surface p-4">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="mb-3 text-xs text-ink-muted">{sub}</p>
      {sorted.length === 0 ? (
        <p className="py-6 text-center text-xs text-ink-muted">No data to show.</p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={sorted} layout="vertical" margin={{ left: 4, right: 20, top: 0, bottom: 0 }}>
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
            <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={16}>
              {sorted.map((row) => (
                <Cell key={row.name} fill={row.color} />
              ))}
              <LabelList
                dataKey="value"
                position="right"
                style={{ fontSize: 11, fill: "var(--color-ink-2)" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
