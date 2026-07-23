/**
 * CSV file picker + drag-and-drop. Fires onFile() with the raw File;
 * all validation (missing feedback column, empty rows, etc.) happens
 * server-side in POST /analyze — this component never inspects file
 * contents itself (frontend/CLAUDE.md, golden rule 2: one request).
 */

import { useRef, useState } from "react";
import type { AnalyzeStatus } from "../hooks/useAnalyze";

interface UploadPanelProps {
  status: AnalyzeStatus;
  fileName: string | null;
  onFile: (file: File) => void;
}

export default function UploadPanel({ status, fileName, onFile }: UploadPanelProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const isLoading = status === "loading";

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (file) onFile(file);
  }

  return (
    <div
      className={`flex items-center gap-3 rounded-xl border px-4 py-3 transition-colors ${
        isDragging ? "border-accent bg-accent/5" : "border-hairline bg-surface"
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">
            {fileName ? `Batch from "${fileName}"` : "Upload a CSV to analyze"}
          </p>
          <p className="truncate text-xs text-ink-muted">
            {isLoading
              ? "Validating, redacting, and classifying tickets…"
              : "Drop a CSV here, or choose a file — needs a feedback column"}
          </p>
        </div>
      </div>

      <label className="flex shrink-0 cursor-pointer items-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-accent-ink hover:brightness-110">
        {isLoading ? "Analyzing…" : "Choose file"}
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="sr-only"
          disabled={isLoading}
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </label>
    </div>
  );
}
