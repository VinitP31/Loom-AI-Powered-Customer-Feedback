/**
 * The 10 headline KPIs from frontend/CLAUDE.md's Components table. Every
 * value is either read straight off `analytics`/`validation_report` or a
 * simple share computed against `processed` (never `total_rows`, never a
 * client-side recomputation of an analytic the backend already sends).
 */

import { useRef, type CSSProperties, type KeyboardEvent, type MouseEvent } from "react";
import type { Analytics, ValidationReport } from "../types/analyze";
import type { Category, Sentiment, Theme, Urgency } from "../types/taxonomy";
import { prefersReducedMotion } from "../utils/motion";

interface KpiCardsProps {
  analytics: Analytics;
  validationReport: ValidationReport;
  activeSentiment: Sentiment | "All";
  activeUrgency: Urgency | "All";
  activeActionable: "All" | "Yes" | "No";
  activeCategory: Category | "All";
  activeTheme: Theme | "All";
  onSentimentClick: (sentiment: Sentiment) => void;
  onHighUrgencyClick: () => void;
  onActionableClick: () => void;
  onNeedsReviewClick: () => void;
  onTopCategoryClick: (category: Category) => void;
  onTopThemeClick: (theme: Theme) => void;
}

interface Kpi {
  label: string;
  value: string;
  sub?: string;
  tone?: "critical" | "warning" | "good";
  tieList?: string[];
  icon: string;
  onClick?: () => void;
  active?: boolean;
}

const TONE_CLASS: Record<NonNullable<Kpi["tone"]>, string> = {
  critical: "text-critical",
  warning: "text-warning",
  good: "text-good",
};

const TONE_VAR: Record<NonNullable<Kpi["tone"]>, string> = {
  critical: "var(--color-critical)",
  warning: "var(--color-warning)",
  good: "var(--color-good)",
};

/** One small glyph per KPI so the grid reads faster than text-only labels —
 * purely decorative, never a stand-in for the label/value text itself. */
const ICONS: Record<string, string> = {
  "Total Feedback": "M4 6h16M4 12h16M4 18h10",
  "Skipped Rows": "M6 6l12 12M18 6L6 18",
  Positive: "M12 19V5M5 12l7-7 7 7",
  Negative: "M12 5v14M5 12l7 7 7-7",
  "Top Category": "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  "Top Theme": "M4 4h16v16H4zM4 10h16",
  "High Urgency": "M12 9v4M12 17h.01M10.3 3.9L2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  Actionable: "M20 6L9 17l-5-5",
  "Needs Review": "M12 8v4l3 3M21 12a9 9 0 1 1-9-9",
  "Success Rate": "M3 12a9 9 0 1 0 9-9M3 3v6h6",
};

export default function KpiCards({
  analytics: a,
  validationReport: v,
  activeSentiment,
  activeUrgency,
  activeActionable,
  activeCategory,
  activeTheme,
  onSentimentClick,
  onHighUrgencyClick,
  onActionableClick,
  onNeedsReviewClick,
  onTopCategoryClick,
  onTopThemeClick,
}: KpiCardsProps) {
  const highUrgencyPct = v.processed ? ((a.high_urgency_count / v.processed) * 100).toFixed(1) : "0.0";

  const kpis: Kpi[] = [
    { label: "Total Feedback", value: String(v.total_rows), sub: `${v.processed} processed`, icon: ICONS["Total Feedback"] },
    { label: "Skipped Rows", value: String(v.skipped), icon: ICONS["Skipped Rows"] },
    {
      label: "Positive",
      value: `${(a.sentiment_distribution_pct.Positive ?? 0).toFixed(1)}%`,
      sub: `${a.sentiment_distribution.Positive ?? 0} tickets`,
      tone: "good",
      icon: ICONS.Positive,
      onClick: () => onSentimentClick("Positive"),
      active: activeSentiment === "Positive",
    },
    {
      label: "Negative",
      value: `${(a.sentiment_distribution_pct.Negative ?? 0).toFixed(1)}%`,
      sub: `${a.sentiment_distribution.Negative ?? 0} tickets`,
      tone: "critical",
      icon: ICONS.Negative,
      onClick: () => onSentimentClick("Negative"),
      active: activeSentiment === "Negative",
    },
    a.top_category
      ? {
          label: "Top Category",
          value: a.top_category,
          icon: ICONS["Top Category"],
          onClick: () => onTopCategoryClick(a.top_category as Category),
          active: activeCategory === a.top_category,
        }
      : { label: "Top Category", value: "Tied", tieList: a.category_leaders, icon: ICONS["Top Category"] },
    a.top_theme
      ? {
          label: "Top Theme",
          value: a.top_theme,
          icon: ICONS["Top Theme"],
          onClick: () => onTopThemeClick(a.top_theme as Theme),
          active: activeTheme === a.top_theme,
        }
      : { label: "Top Theme", value: "Tied", tieList: a.theme_leaders, icon: ICONS["Top Theme"] },
    {
      label: "High Urgency",
      value: String(a.high_urgency_count),
      sub: `${highUrgencyPct}%`,
      tone: "critical",
      icon: ICONS["High Urgency"],
      onClick: onHighUrgencyClick,
      active: activeUrgency === "High",
    },
    {
      label: "Actionable",
      value: `${a.actionable_pct.toFixed(1)}%`,
      sub: `${a.actionable_count} tickets`,
      tone: "good",
      icon: ICONS.Actionable,
      onClick: onActionableClick,
      active: activeActionable === "Yes",
    },
    {
      label: "Needs Review",
      value: String(a.fell_back_count),
      sub: "fell back to review",
      tone: a.fell_back_count > 0 ? "warning" : undefined,
      icon: ICONS["Needs Review"],
      onClick: a.fell_back_count > 0 ? onNeedsReviewClick : undefined,
      active: activeTheme === "Requires Human Review",
    },
    {
      label: "Success Rate",
      value: `${a.processing_success_rate.toFixed(1)}%`,
      sub: `${v.processed} of ${v.total_rows}`,
      tone: "good",
      icon: ICONS["Success Rate"],
    },
  ];

  const fieldRef = useRef<HTMLDivElement>(null);

  function handleFieldMouseMove(e: MouseEvent<HTMLDivElement>) {
    if (prefersReducedMotion()) return;
    const field = fieldRef.current;
    if (!field) return;
    const r = field.getBoundingClientRect();
    field.style.setProperty("--glow-x", `${e.clientX - r.left}px`);
    field.style.setProperty("--glow-y", `${e.clientY - r.top}px`);
  }

  function handleCardMouseMove(e: MouseEvent<HTMLDivElement>) {
    if (prefersReducedMotion()) return;
    const card = e.currentTarget;
    const r = card.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    card.style.transform = `translateY(-4px) scale(1.02) rotateY(${px * 16}deg) rotateX(${-py * 16}deg)`;
  }

  function handleCardMouseLeave(e: MouseEvent<HTMLDivElement>) {
    e.currentTarget.style.transform = "";
  }

  return (
    <div
      ref={fieldRef}
      onMouseMove={handleFieldMouseMove}
      className="kpi-spotlight-field relative overflow-hidden rounded-xl border border-hairline bg-surface-2 p-3"
    >
      <div className="kpi-spotlight-glow pointer-events-none absolute rounded-full" aria-hidden="true" />
      <div className="relative grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" style={{ perspective: "900px" }}>
        {kpis.map((kpi, i) => (
          <div
            key={kpi.label}
            role={kpi.onClick ? "button" : undefined}
            tabIndex={kpi.onClick ? 0 : undefined}
            onClick={kpi.onClick}
            onKeyDown={
              kpi.onClick
                ? (e: KeyboardEvent<HTMLDivElement>) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      kpi.onClick?.();
                    }
                  }
                : undefined
            }
            title={kpi.onClick ? "Click to filter the ticket table" : undefined}
            className={`kpi-card group relative overflow-hidden rounded-lg border py-2 pl-4 pr-3 will-change-transform hover:shadow-[0_16px_30px_-14px_rgba(0,0,0,0.32)] hover:border-[color-mix(in_oklab,var(--tone,var(--color-accent))_45%,var(--color-hairline))] ${
              kpi.onClick ? "cursor-pointer" : ""
            } ${kpi.active ? "border-[var(--tone,var(--color-accent))] ring-2 ring-[color-mix(in_oklab,var(--tone,var(--color-accent))_35%,transparent)]" : "border-hairline"}`}
            style={{ "--tone": kpi.tone ? TONE_VAR[kpi.tone] : undefined, animationDelay: `${i * 40}ms` } as CSSProperties}
            onMouseMove={handleCardMouseMove}
            onMouseLeave={handleCardMouseLeave}
          >
            <span
              className="pointer-events-none absolute inset-y-0 left-0 w-[3px] rounded-l-lg"
              style={{ background: kpi.tone ? TONE_VAR[kpi.tone] : "var(--color-accent)" }}
              aria-hidden="true"
            />
            <span className="kpi-shine pointer-events-none absolute inset-0" aria-hidden="true" />
            <div className="flex items-center justify-between gap-2">
              <p className="text-[10.5px] font-medium text-ink-muted">{kpi.label}</p>
              <span
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md transition-transform duration-200 group-hover:scale-110"
                style={{
                  background: `color-mix(in oklab, ${kpi.tone ? TONE_VAR[kpi.tone] : "var(--color-accent)"} 14%, transparent)`,
                  color: kpi.tone ? TONE_VAR[kpi.tone] : "var(--color-accent)",
                }}
              >
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d={kpi.icon} />
                </svg>
              </span>
            </div>
            <p className={`mt-1 text-lg font-bold ${kpi.tone ? TONE_CLASS[kpi.tone] : "text-ink"}`}>{kpi.value}</p>
            {kpi.tieList ? (
              <p className="mt-0.5 text-[10.5px] leading-snug text-ink-2">Tied: {kpi.tieList.join(", ")}</p>
            ) : (
              kpi.sub && <p className="mt-0.5 text-[10.5px] text-ink-muted">{kpi.sub}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
