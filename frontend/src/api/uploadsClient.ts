/**
 * Typed client for the history/persistence read endpoints — GET /uploads
 * (list, for the sidebar) and GET /uploads/{id} (one past upload's own
 * dashboard, read-only replay). Separate from analyzeClient.ts's single
 * POST /analyze since these are plain reads, not part of the
 * upload -> analyze -> render flow (frontend/CLAUDE.md golden rule 2 is
 * about /analyze specifically; these two exist only for the history
 * sidebar and never call the LLM).
 */

import type { HistoricalSnapshot, UploadSummary } from "../types/analyze";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchUploadHistory(): Promise<UploadSummary[]> {
  const response = await fetch(`${API_BASE_URL}/uploads`);
  if (!response.ok) {
    throw new Error(`Could not load upload history (HTTP ${response.status}).`);
  }
  return (await response.json()) as UploadSummary[];
}

export async function fetchUploadSnapshot(id: number): Promise<HistoricalSnapshot> {
  const response = await fetch(`${API_BASE_URL}/uploads/${id}`);
  if (!response.ok) {
    throw new Error(`Could not load upload #${id} (HTTP ${response.status}).`);
  }
  return (await response.json()) as HistoricalSnapshot;
}

export async function deleteUpload(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/uploads/${id}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`Could not delete upload #${id} (HTTP ${response.status}).`);
  }
}
