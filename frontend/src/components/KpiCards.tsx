/**
 * The 10 headline KPIs from frontend/CLAUDE.md's Components table. Every
 * value is either read straight off `analytics`/`validation_report` or a
 * simple share computed against `processed` (never `total_rows`, never a
 * client-side recomputation of an analytic the backend already sends).
 */

import type { Analytics, ValidationReport } from "../types/analyze";

interface KpiCardsProps {
  analytics: Analytics;
  validationReport: ValidationReport;
}

interface Kpi {
  label: string;
  value: string;
  sub?: string;
  tone?: "critical" | "warning" | "good";
  tieList?: string[];
}

const TONE_CLASS: Record<NonNullable<Kpi["tone"]>, string> = {
  critical: "text-critical",
  warning: "text-warning",
  good: "text-good",
};

export default function KpiCards({ analytics: a, validationReport: v }: KpiCardsProps) {
  const highUrgencyPct = v.processed ? ((a.high_urgency_count / v.processed) * 100).toFixed(1) : "0.0";

  const kpis: Kpi[] = [
    { label: "Total Feedback", value: String(v.total_rows), sub: `${v.processed} processed` },
    { label: "Skipped Rows", value: String(v.skipped) },
    {
      label: "Positive",
      value: `${(a.sentiment_distribution_pct.Positive ?? 0).toFixed(1)}%`,
      sub: `${a.sentiment_distribution.Positive ?? 0} tickets`,
      tone: "good",
    },
    {
      label: "Negative",
      value: `${(a.sentiment_distribution_pct.Negative ?? 0).toFixed(1)}%`,
      sub: `${a.sentiment_distribution.Negative ?? 0} tickets`,
      tone: "critical",
    },
    a.top_category
      ? { label: "Top Category", value: a.top_category }
      : { label: "Top Category", value: "Tied", tieList: a.category_leaders },
    a.top_theme
      ? { label: "Top Theme", value: a.top_theme }
      : { label: "Top Theme", value: "Tied", tieList: a.theme_leaders },
    { label: "High Urgency", value: String(a.high_urgency_count), sub: `${highUrgencyPct}%`, tone: "critical" },
    { label: "Actionable", value: `${a.actionable_pct.toFixed(1)}%`, sub: `${a.actionable_count} tickets`, tone: "good" },
    {
      label: "Needs Review",
      value: String(a.fell_back_count),
      sub: "fell back to review",
      tone: a.fell_back_count > 0 ? "warning" : undefined,
    },
    { label: "Success Rate", value: `${a.processing_success_rate.toFixed(1)}%`, sub: `${v.processed} of ${v.total_rows}`, tone: "good" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {kpis.map((kpi) => (
        <div key={kpi.label} className="rounded-lg border border-hairline bg-surface px-4 py-3">
          <p className="text-[11px] font-medium text-ink-muted">{kpi.label}</p>
          <p className={`mt-1.5 text-xl font-bold ${kpi.tone ? TONE_CLASS[kpi.tone] : "text-ink"}`}>
            {kpi.value}
          </p>
          {kpi.tieList ? (
            <p className="mt-1 text-[11px] leading-snug text-ink-2">Tied: {kpi.tieList.join(", ")}</p>
          ) : (
            kpi.sub && <p className="mt-1 text-[11px] text-ink-muted">{kpi.sub}</p>
          )}
        </div>
      ))}
    </div>
  );
}
