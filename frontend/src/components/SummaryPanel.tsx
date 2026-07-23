/**
 * Renders the backend's grounded executive summary verbatim. The
 * frontend never generates, edits, or re-derives this text — it's a
 * single LLM call over Python-computed facts (Loom_Source_of_Truth.md,
 * Executive Summary stage); this component is a pure display.
 */

interface SummaryPanelProps {
  summary: string;
}

export default function SummaryPanel({ summary }: SummaryPanelProps) {
  if (!summary) return null;

  return (
    <div className="rounded-lg border border-hairline bg-surface p-4">
      <h3 className="text-sm font-semibold text-ink">Executive Summary</h3>
      <p className="mt-2 text-sm leading-relaxed text-ink-2">{summary}</p>
    </div>
  );
}
