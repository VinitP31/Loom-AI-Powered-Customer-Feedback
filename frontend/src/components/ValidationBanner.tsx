/**
 * Surfaces validation_report as a small status line — total/processed/
 * skipped rows plus fell_back_count as a quality signal ("needs review"),
 * never folded into any distribution or percentage
 * (frontend/CLAUDE.md, golden rule 5).
 */

import type { ValidationReport } from "../types/analyze";

interface ValidationBannerProps {
  report: ValidationReport;
}

export default function ValidationBanner({ report }: ValidationBannerProps) {
  const skipReasonEntries = Object.entries(report.skip_reasons);

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-lg border border-hairline bg-surface-2 px-4 py-2.5 text-xs text-ink-2">
      <span>
        <strong className="font-semibold text-ink">{report.total_rows}</strong> rows uploaded
      </span>
      <span>
        <strong className="font-semibold text-ink">{report.processed}</strong> processed
      </span>
      <span>
        <strong className="font-semibold text-ink">{report.skipped}</strong> skipped
        {skipReasonEntries.length > 0 && (
          <span className="text-ink-muted">
            {" "}
            ({skipReasonEntries.map(([reason, count]) => `${count} ${reason.replace(/_/g, " ")}`).join(", ")})
          </span>
        )}
      </span>
      {report.fell_back_count > 0 && (
        <span>
          <strong className="font-semibold text-warning">{report.fell_back_count}</strong>{" "}
          <span className="text-ink-muted">needed human review</span>
        </span>
      )}
    </div>
  );
}
