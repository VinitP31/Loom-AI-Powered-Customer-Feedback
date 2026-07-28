/**
 * Automatic "vs last week" section on the live (latest) upload's
 * dashboard — never shown on a historical replay (that's a past week's
 * own dashboard, not a diff). Renders backend/storage/compare.py's
 * already-computed deltas; nothing here is recomputed client-side, same
 * rule as every other chart (frontend/CLAUDE.md golden rule 4).
 *
 * Each tile shows the before -> after values, not a bare delta — "-36.7%"
 * alone doesn't say what it moved from/to. A small two-bar mini chart
 * makes the shift scannable without needing a 3+ point trend line, which
 * a single previous-upload comparison doesn't have enough data for.
 */

import type { Comparison } from "../types/analyze";

interface WeekComparisonProps {
  comparison: Comparison;
}

/** Whether a positive delta on this metric is good, bad, or genuinely
 * neutral news — a raw sign check gets this backwards for "lower is
 * better" metrics (e.g. High Urgency dropping is good, so a NEGATIVE
 * delta there should read green, not red). */
type Direction = "upIsGood" | "downIsGood" | "neutral";

function formatUploadedAt(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function toneClass(delta: number, direction: Direction): string {
  if (delta === 0 || direction === "neutral") return "text-ink-muted";
  const isGood = direction === "upIsGood" ? delta > 0 : delta < 0;
  return isGood ? "text-good" : "text-critical";
}

function tileToneClass(delta: number, direction: Direction): string {
  if (delta === 0 || direction === "neutral") return "border-l-ink-muted/30";
  const isGood = direction === "upIsGood" ? delta > 0 : delta < 0;
  return isGood ? "border-l-good" : "border-l-critical";
}

function MiniBars({ before, after, tone }: { before: number; after: number; tone: "good" | "bad" | "neutral" }) {
  const max = Math.max(before, after, 1);
  const color = tone === "good" ? "bg-good" : tone === "bad" ? "bg-critical" : "bg-ink-muted";
  return (
    <div className="mt-1.5 flex items-end gap-1.5">
      <div className="flex flex-1 flex-col gap-0.5">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
          <div className="h-full rounded-full bg-ink-muted/50" style={{ width: `${(before / max) * 100}%` }} />
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${(after / max) * 100}%` }} />
        </div>
      </div>
    </div>
  );
}

function Tile({
  label,
  before,
  after,
  delta,
  direction,
  suffix = "%",
}: {
  label: string;
  before: number;
  after: number;
  delta: number;
  direction: Direction;
  suffix?: string;
}) {
  const tone: "good" | "bad" | "neutral" =
    delta === 0 || direction === "neutral" ? "neutral" : (direction === "upIsGood" ? delta > 0 : delta < 0) ? "good" : "bad";
  const arrow = delta === 0 ? "" : delta > 0 ? "▲ " : "▼ ";
  return (
    <div className={`rounded-md border-l-[3px] bg-surface-2 px-2.5 py-2 ${tileToneClass(delta, direction)}`}>
      <p className="text-[10.5px] text-ink-muted">{label}</p>
      <p className="text-sm font-semibold">
        <span className="text-ink-muted">
          {before}
          {suffix}
        </span>
        <span className="mx-1 text-ink-muted">→</span>
        <span className={toneClass(delta, direction)}>
          {after}
          {suffix}
        </span>
      </p>
      <p className={`text-[10.5px] ${toneClass(delta, direction)}`}>
        {delta === 0 ? "No change" : `${arrow}${Math.abs(delta)}${suffix}`}
      </p>
      <MiniBars before={before} after={after} tone={tone} />
    </div>
  );
}

function ThemeChips({ label, themes, tone }: { label: string; themes: string[]; tone: "good" | "critical" }) {
  if (themes.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-[10.5px] font-medium text-ink-muted">{label}:</span>
      {themes.map((theme) => (
        <span
          key={theme}
          className={`rounded-full px-2 py-0.5 text-[10.5px] ${
            tone === "good" ? "bg-good/12 text-good" : "bg-critical/12 text-critical"
          }`}
        >
          {theme}
        </span>
      ))}
    </div>
  );
}

// Direction per urgency/sentiment label — a "bad" bucket shrinking is
// good news (downIsGood); a "good" bucket growing is good news (upIsGood).
const SENTIMENT_DIRECTION: Record<string, Direction> = {
  Positive: "upIsGood",
  Neutral: "neutral",
  Negative: "downIsGood",
};
const URGENCY_DIRECTION: Record<string, Direction> = {
  High: "downIsGood",
  Medium: "downIsGood",
  Low: "upIsGood",
};

export default function WeekComparison({ comparison }: WeekComparisonProps) {
  const sentimentLabels = Object.keys(comparison.sentiment_shift_pct);
  // "High" is excluded here — it's already the dedicated "High Urgency"
  // headline tile below (same underlying number), so including it too
  // would render "High Urgency" twice with identical values.
  const urgencyLabels = Object.keys(comparison.urgency_shift_count).filter((label) => label !== "High");

  return (
    <section className="flex flex-col gap-2.5 rounded-lg border border-hairline bg-surface p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold text-ink">Vs Last Week</h2>
        <span className="text-[10.5px] text-ink-muted">
          compared to upload on {formatUploadedAt(comparison.previous_uploaded_at)}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Tile
          label="High Urgency"
          before={comparison.high_urgency_count_before}
          after={comparison.high_urgency_count_after}
          delta={comparison.high_urgency_count_delta}
          direction="downIsGood"
          suffix=" tickets"
        />
        <Tile
          label="Actionable"
          before={comparison.actionable_pct_before}
          after={comparison.actionable_pct_after}
          delta={comparison.actionable_pct_delta}
          direction="upIsGood"
        />
        {sentimentLabels.map((label) => (
          <Tile
            key={label}
            label={`${label} Sentiment`}
            before={comparison.sentiment_pct_before[label as keyof typeof comparison.sentiment_pct_before] ?? 0}
            after={comparison.sentiment_pct_after[label as keyof typeof comparison.sentiment_pct_after] ?? 0}
            delta={comparison.sentiment_shift_pct[label as keyof typeof comparison.sentiment_shift_pct] ?? 0}
            direction={SENTIMENT_DIRECTION[label] ?? "neutral"}
          />
        ))}
        {urgencyLabels.map((label) => (
          <Tile
            key={label}
            label={`${label} Urgency`}
            before={comparison.urgency_count_before[label as keyof typeof comparison.urgency_count_before] ?? 0}
            after={comparison.urgency_count_after[label as keyof typeof comparison.urgency_count_after] ?? 0}
            delta={comparison.urgency_shift_count[label as keyof typeof comparison.urgency_shift_count] ?? 0}
            direction={URGENCY_DIRECTION[label] ?? "neutral"}
            suffix=" tickets"
          />
        ))}
      </div>

      {(comparison.new_themes.length > 0 || comparison.disappeared_themes.length > 0) && (
        <div className="flex flex-col gap-1.5 border-t border-hairline pt-2">
          <ThemeChips label="First seen this week" themes={comparison.new_themes} tone="critical" />
          <ThemeChips label="Not seen this week" themes={comparison.disappeared_themes} tone="good" />
        </div>
      )}
    </section>
  );
}
