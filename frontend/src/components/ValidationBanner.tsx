/**
 * Surfaces validation_report as a small status line — total/processed/
 * skipped rows plus fell_back_count as a quality signal ("needs review"),
 * never folded into any distribution or percentage
 * (frontend/CLAUDE.md, golden rule 5). Skipped/needs-review are rendered
 * as their own labeled, bordered toggle chips (not a bare underlined
 * number buried in a sentence) — a visible chevron + hover state makes
 * "this expands" obvious at a glance, and the whole chip is the hit
 * target, not just the digit.
 */

import { useState } from "react";
import type { TicketClassification, ValidationReport } from "../types/analyze";

interface ValidationBannerProps {
  report: ValidationReport;
  items: TicketClassification[];
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      width="11"
      height="11"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 transition-transform duration-150 ${open ? "rotate-180" : ""}`}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

export default function ValidationBanner({ report, items }: ValidationBannerProps) {
  const [open, setOpen] = useState<"skipped" | "review" | null>(null);
  const skipReasonEntries = Object.entries(report.skip_reasons);
  const needsReview = items.filter((item) => item.primary_theme === "Requires Human Review");

  return (
    <div className="rounded-lg border border-hairline bg-surface-2 text-xs text-ink-2">
      <div className="flex flex-wrap items-center gap-2 px-4 py-2.5">
        <span>
          <strong className="font-semibold text-ink">{report.total_rows}</strong> rows uploaded
        </span>
        <span className="text-hairline">·</span>
        <span>
          <strong className="font-semibold text-ink">{report.processed}</strong> processed
        </span>

        {report.skipped > 0 && (
          <button
            type="button"
            onClick={() => setOpen((o) => (o === "skipped" ? null : "skipped"))}
            aria-expanded={open === "skipped"}
            className={`ml-1 flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-semibold transition-colors ${
              open === "skipped"
                ? "border-accent bg-accent/10 text-accent"
                : "border-hairline bg-surface text-ink hover:border-accent/40 hover:text-accent"
            }`}
          >
            {report.skipped} skipped
            {skipReasonEntries.length > 0 && (
              <span className="font-normal text-ink-muted">
                ({skipReasonEntries.map(([reason, count]) => `${count} ${reason.replace(/_/g, " ")}`).join(", ")})
              </span>
            )}
            <Chevron open={open === "skipped"} />
          </button>
        )}

        {report.fell_back_count > 0 && (
          <button
            type="button"
            onClick={() => setOpen((o) => (o === "review" ? null : "review"))}
            aria-expanded={open === "review"}
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-semibold transition-colors ${
              open === "review"
                ? "border-warning bg-warning/10 text-warning"
                : "border-hairline bg-surface text-warning hover:border-warning/40"
            }`}
          >
            {report.fell_back_count} needs review
            <Chevron open={open === "review"} />
          </button>
        )}
      </div>

      {open === "skipped" && (
        <div className="border-t border-hairline bg-surface px-4 py-3">
          <p className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-ink-muted">
            Skipped rows — never counted in analytics
          </p>
          <ul className="flex flex-col gap-1">
            {report.skipped_rows.map((row) => (
              <li key={row.ticket_id} className="flex items-center gap-2">
                <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-ink">
                  {row.ticket_id}
                </span>
                <span className="text-ink-muted">{row.reason.replace(/_/g, " ")}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {open === "review" && (
        <div className="border-t border-hairline bg-surface px-4 py-3">
          <p className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-ink-muted">
            Fell back to "Requires Human Review" — a quality signal, not an error
          </p>
          <ul className="flex flex-col gap-1.5">
            {needsReview.map((item) => (
              <li key={item.ticket_id} className="flex items-start gap-2">
                <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-ink">
                  {item.ticket_id}
                </span>
                <span className="line-clamp-1 text-ink-2">{item.feedback_text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
