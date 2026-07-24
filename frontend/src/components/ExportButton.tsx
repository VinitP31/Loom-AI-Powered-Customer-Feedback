/**
 * Exports the current analysis as a PDF report — KPIs, the four
 * distributions, and the executive summary (never the raw ticket list;
 * that's already searchable in FeedbackExplorer). Pure client-side
 * formatting of the existing payload — no new request, no
 * recomputation (see utils/exportReport.ts).
 */

import type { AnalyzeResponse } from "../types/analyze";
import { exportReportPdf } from "../utils/exportReport";

interface ExportButtonProps {
  data: AnalyzeResponse;
  fileName: string | null;
}

export default function ExportButton({ data, fileName }: ExportButtonProps) {
  return (
    <button
      type="button"
      onClick={() => exportReportPdf(data, fileName)}
      className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-[#4338ca] to-[#9333ea] px-4 py-2 text-xs font-semibold text-white shadow-md shadow-purple-900/20 transition hover:-translate-y-0.5 hover:shadow-lg active:translate-y-0 active:shadow-sm"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M9 15h6M9 12h3" />
      </svg>
      Export PDF
    </button>
  );
}
