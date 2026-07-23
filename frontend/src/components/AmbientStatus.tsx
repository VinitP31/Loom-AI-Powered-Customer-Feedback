/**
 * Replaces the old boxed dropzone card with a borderless status line —
 * an equalizer icon + batch label + a stage word, matching the frozen
 * Structured Data Studio concept (studio-full.html) rather than a
 * "nothing more there" empty upload screen. The stage word only cycles
 * while a real request is in flight ("processing" theater tied to actual
 * work) — it freezes on a final word once the dashboard is showing,
 * rather than animating forever regardless of what's on screen. Still
 * accepts a dropped file since the drop target doesn't need a visible
 * border to function.
 */

import { useEffect, useRef, useState } from "react";
import type { AnalyzeStatus } from "../hooks/useAnalyze";

interface AmbientStatusProps {
  status: AnalyzeStatus;
  fileName: string | null;
  onFile: (file: File) => void;
}

const STAGES = ["Validating rows…", "Redacting PII…", "Classifying tickets…", "Computing analytics…", "Writing summary…"];

const FINAL_STAGE_TEXT: Record<Exclude<AnalyzeStatus, "loading">, string> = {
  idle: "Ready",
  success: "Done",
  error: "Failed",
};

function reduceMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function AmbientStatus({ status, fileName, onFile }: AmbientStatusProps) {
  const [stageIndex, setStageIndex] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isLoading = status === "loading";

  useEffect(() => {
    if (!isLoading || reduceMotion()) return;
    setStageIndex(0);
    timerRef.current = setInterval(() => {
      setStageIndex((i) => (i + 1) % STAGES.length);
    }, 340);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isLoading]);

  const label = fileName ? `Batch from "${fileName}"` : "No batch analyzed yet";
  const stageText = isLoading ? STAGES[stageIndex] : FINAL_STAGE_TEXT[status];

  return (
    <div
      className={`flex items-center gap-3 px-6 py-4 text-xs transition-colors ${isDragging ? "text-accent" : "text-ink-muted"}`}
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
      <span className={isLoading ? "ambient-cycle-text" : undefined}>{stageText}</span>
    </div>
  );
}
