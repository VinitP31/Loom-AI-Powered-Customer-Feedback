/**
 * Renders the backend's grounded executive summary verbatim. The
 * frontend never generates, edits, or re-derives this text — it's a
 * single LLM call over Python-computed facts (Loom_Source_of_Truth.md,
 * Executive Summary stage); this component is a pure display.
 *
 * Collapsed by default: the panel sits in a narrow sticky sidebar, so a
 * full paragraph of prose can render taller than the entire chart column
 * next to it. Clamping to a few lines with a "Show more" toggle keeps the
 * layout balanced without ever hiding the text — it's one click away.
 */

import { useState } from "react";

interface SummaryPanelProps {
  summary: string;
}

// Roughly the point a summary stops fitting in ~6 lines at the sidebar's
// width — below this, clamping (and the toggle) would just be noise.
const CLAMP_THRESHOLD = 260;

export default function SummaryPanel({ summary }: SummaryPanelProps) {
  const [expanded, setExpanded] = useState(false);

  if (!summary) return null;

  const needsClamp = summary.length > CLAMP_THRESHOLD;

  return (
    <div className="rounded-lg border border-hairline bg-surface p-4">
      <h3 className="text-sm font-semibold text-ink">Executive Summary</h3>
      <p className={`mt-2 text-[13px] leading-relaxed text-ink-2 ${needsClamp && !expanded ? "line-clamp-6" : ""}`}>
        {summary}
      </p>
      {needsClamp && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-2 text-[11.5px] font-semibold text-accent hover:underline"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}
