/**
 * The first thing a stakeholder should read — one sentence, lead with the
 * conclusion, before any chart or table. Every number here is read
 * straight off `analytics`/`validation_report` (already backend-computed,
 * already denominated against `processed`) — this only composes them into
 * a sentence, never recomputes a percentage or aggregate itself.
 */

import type { Analytics, ValidationReport } from "../types/analyze";

interface HeadlineSummaryProps {
  analytics: Analytics;
  validationReport: ValidationReport;
}

export default function HeadlineSummary({ analytics: a, validationReport: v }: HeadlineSummaryProps) {
  const topIssue = a.top_category ?? (a.category_leaders.length ? a.category_leaders.join(" & ") : null);
  const negativePct = (a.sentiment_distribution_pct.Negative ?? 0).toFixed(1);

  return (
    <div className="flex items-center gap-3 rounded-lg border border-hairline bg-surface px-4 py-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent/10 text-accent" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M13 2 3 14h7l-1 8 10-12h-7l1-8z" />
        </svg>
      </span>
      <p className="text-sm leading-relaxed text-ink">
        <span className="font-bold">{v.processed} tickets analyzed.</span>{" "}
        {topIssue && (
          <>
            Top issue: <span className="font-semibold">{topIssue}</span>.{" "}
          </>
        )}
        <span className={a.sentiment_distribution_pct.Negative ? "font-semibold text-critical" : "font-semibold"}>
          {negativePct}% negative
        </span>
        {", "}
        <span className={a.high_urgency_count > 0 ? "font-semibold text-critical" : "font-semibold"}>
          {a.high_urgency_count} high-urgency
        </span>
        {", "}
        <span className="font-semibold text-good">{a.actionable_pct.toFixed(1)}% actionable</span>.
      </p>
    </div>
  );
}
