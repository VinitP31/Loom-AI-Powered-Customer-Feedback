/**
 * Replaces the old boxed dropzone card with a borderless status line —
 * an equalizer icon + batch label + a stage word, matching the frozen
 * Structured Data Studio concept (studio-full.html) rather than a
 * "nothing more there" empty upload screen. The stage text reflects real
 * backend progress (streamed off /analyze — see useAnalyze's `progress`)
 * once classification starts; before the first ticket finishes
 * (validation/redaction — brief) it shows a static "Validating…" label
 * rather than a fake cycling animation. Still accepts a dropped file
 * since the drop target doesn't need a visible border to function.
 */

import type { AnalyzeProgress } from "../api/analyzeClient";
import { useState } from "react";
import type { AnalyzeStatus } from "../hooks/useAnalyze";

interface AmbientStatusProps {
  status: AnalyzeStatus;
  fileName: string | null;
  progress: AnalyzeProgress | null;
  onFile: (file: File) => void;
}

const FINAL_STAGE_TEXT: Record<Exclude<AnalyzeStatus, "loading">, string> = {
  idle: "Ready",
  success: "Done",
  error: "Failed",
};

const PROGRESS_STAGE_LABEL: Record<AnalyzeProgress["stage"], string> = {
  classifying: "Classifying tickets",
  summarizing: "Writing summary",
};

export default function AmbientStatus({ status, fileName, progress, onFile }: AmbientStatusProps) {
  const [isDragging, setIsDragging] = useState(false);
  const isLoading = status === "loading";

  const label = fileName ? `Batch from "${fileName}"` : "No batch analyzed yet";
  const stageText = isLoading
    ? progress
      ? `${PROGRESS_STAGE_LABEL[progress.stage]}… ${progress.done}/${progress.total}`
      : "Validating & redacting…"
    : FINAL_STAGE_TEXT[status];

  return (
    <div
      className={`flex items-center gap-3 rounded-lg border border-dashed px-6 py-4 text-xs transition-colors ${
        isDragging ? "border-accent bg-accent/5 text-accent" : "border-transparent text-ink-muted"
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
    >
      <span className="flex h-3.5 items-end gap-0.5" aria-hidden="true">
        <span className={`h-1.5 w-0.5 rounded-sm bg-accent ${isLoading ? "ambient-eq-bar" : ""}`} style={{ animationDelay: "0s" }} />
        <span className={`h-3.5 w-0.5 rounded-sm bg-accent ${isLoading ? "ambient-eq-bar" : ""}`} style={{ animationDelay: "0.2s" }} />
        <span className={`h-2 w-0.5 rounded-sm bg-accent ${isLoading ? "ambient-eq-bar" : ""}`} style={{ animationDelay: "0.4s" }} />
      </span>
      <span className="font-semibold text-ink-2">{label}</span>
      <span className="text-ink-muted/70">·</span>
      <span>{isDragging ? "Drop to analyze" : stageText}</span>
    </div>
  );
}
