/**
 * Claude/ChatGPT-style history list, persistent across views — every
 * upload is saved automatically (backend/storage), this just lists them
 * newest first. Clicking an entry replays that week's own dashboard
 * read-only; clicking "Current" (or the already-selected entry again)
 * returns to the live upload. Each row also has a delete icon — a
 * two-step confirm (icon → "Sure? Yes/No" replacing the row briefly)
 * since deleting a snapshot is irreversible, before calling removeUpload().
 * Purely a list + selection + delete-confirm UI — the actual
 * fetch/replay/delete logic lives in useUploadHistory().
 */

import { type KeyboardEvent, useState } from "react";
import type { UploadSummary } from "../types/analyze";

interface HistorySidebarProps {
  uploads: UploadSummary[];
  selectedId: number | null;
  currentUploadId: number | null;
  onSelect: (id: number | null) => void;
  onDelete: (id: number) => void;
}

function formatUploadedAt(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
    " · " +
    date.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export default function HistorySidebar({ uploads, selectedId, currentUploadId, onSelect, onDelete }: HistorySidebarProps) {
  const [confirmingId, setConfirmingId] = useState<number | null>(null);

  if (uploads.length === 0) {
    return null;
  }

  return (
    <aside className="flex flex-col gap-1 border-r border-hairline pr-3">
      <p className="px-1 pb-1 text-[10.5px] font-semibold uppercase tracking-wide text-ink-muted">
        Upload History
      </p>
      <nav className="flex flex-col gap-0.5">
        {uploads.map((upload) => {
          const isCurrent = upload.id === currentUploadId;
          const isSelected = selectedId === null ? isCurrent : selectedId === upload.id;

          if (confirmingId === upload.id) {
            return (
              <div key={upload.id} className="flex items-center justify-between gap-1 rounded-md bg-critical/10 px-2 py-1.5 ring-1 ring-inset ring-critical/30">
                <span className="text-[11px] text-ink">Delete this upload?</span>
                <span className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      onDelete(upload.id);
                      setConfirmingId(null);
                    }}
                    className="rounded bg-critical px-1.5 py-0.5 text-[10px] font-semibold text-white"
                  >
                    Yes
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmingId(null)}
                    className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-semibold text-ink-2"
                  >
                    No
                  </button>
                </span>
              </div>
            );
          }

          return (
            <div
              key={upload.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelect(isCurrent ? null : upload.id)}
              onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(isCurrent ? null : upload.id);
                }
              }}
              aria-current={isSelected ? "true" : undefined}
              title={upload.source_filename}
              className={`group flex items-start justify-between gap-1 rounded-md px-2 py-1.5 text-left text-xs transition-colors cursor-pointer ${
                isSelected
                  ? "bg-accent/12 text-ink ring-1 ring-inset ring-accent/40"
                  : "text-ink-2 hover:bg-surface-2"
              }`}
            >
              <div className="min-w-0 flex-1">
                <span className="block w-full truncate font-medium">{upload.source_filename}</span>
                <span className="text-[10px] text-ink-muted">
                  {formatUploadedAt(upload.uploaded_at)}
                  {isCurrent && " · Current"}
                </span>
              </div>
              <button
                type="button"
                aria-label={`Delete upload ${upload.source_filename}`}
                title="Delete this upload"
                onClick={(e) => {
                  e.stopPropagation();
                  setConfirmingId(upload.id);
                }}
                className="mt-0.5 shrink-0 rounded p-1 text-ink-muted opacity-0 hover:bg-critical/12 hover:text-critical group-hover:opacity-100 focus-visible:opacity-100"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6h16Z" />
                </svg>
              </button>
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
