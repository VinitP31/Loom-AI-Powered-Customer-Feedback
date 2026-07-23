/**
 * Top bar — brand mark left, theme toggle + upload trigger right. Matches
 * the frozen Structured Data Studio design (see the archived
 * studio-full.html concept artifact): the upload action lives here, not
 * in a boxed dropzone card in the page body.
 */

import { useEffect, useState } from "react";
import type { AnalyzeStatus } from "../hooks/useAnalyze";

interface NavProps {
  status: AnalyzeStatus;
  onFile: (file: File) => void;
}

type ThemePref = "light" | "dark";

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export default function Nav({ status, onFile }: NavProps) {
  const [theme, setTheme] = useState<ThemePref>(() => (systemPrefersDark() ? "dark" : "light"));

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const isLoading = status === "loading";

  return (
    <div className="flex items-center justify-between border-b border-hairline bg-surface px-6 py-3">
      <div className="flex items-center gap-2 text-sm font-bold text-ink">
        <span className="h-4.5 w-4.5 rounded-md bg-accent" aria-hidden="true" />
        Loom Studio
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          aria-label="Toggle dark mode"
          title="Toggle dark mode"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-hairline bg-surface-2 text-ink-2"
        >
          {theme === "dark" ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          )}
        </button>
        <label className="flex cursor-pointer items-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-accent-ink hover:brightness-110">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          Upload file
          <input
            type="file"
            accept=".csv"
            className="sr-only"
            disabled={isLoading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onFile(file);
              e.target.value = "";
            }}
          />
        </label>
      </div>
    </div>
  );
}
