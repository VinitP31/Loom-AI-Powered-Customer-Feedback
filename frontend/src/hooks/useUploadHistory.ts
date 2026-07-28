/**
 * Owns the history sidebar's list + the currently-viewed past snapshot
 * (if any). `selectedId === null` means "viewing the live current
 * upload," not "nothing selected" — DashboardPage renders the fresh
 * useAnalyze() result in that case and the read-only replay otherwise.
 */

import { useCallback, useState } from "react";
import { deleteUpload, fetchUploadHistory, fetchUploadSnapshot } from "../api/uploadsClient";
import type { HistoricalSnapshot, UploadSummary } from "../types/analyze";

export interface UseUploadHistoryState {
  uploads: UploadSummary[];
  selectedId: number | null;
  selectedSnapshot: HistoricalSnapshot | null;
  snapshotLoading: boolean;
  snapshotError: string | null;
  deleteError: string | null;
  refreshHistory: () => Promise<void>;
  selectUpload: (id: number | null) => void;
  removeUpload: (id: number) => Promise<void>;
}

export function useUploadHistory(): UseUploadHistoryState {
  const [uploads, setUploads] = useState<UploadSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<HistoricalSnapshot | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    try {
      setUploads(await fetchUploadHistory());
    } catch {
      // History sidebar is a convenience, not the primary flow — a failed
      // refresh just leaves the list stale, never blocks the dashboard.
    }
  }, []);

  const selectUpload = useCallback((id: number | null) => {
    setSelectedId(id);
    if (id === null) {
      setSelectedSnapshot(null);
      setSnapshotError(null);
      return;
    }
    setSnapshotLoading(true);
    setSnapshotError(null);
    fetchUploadSnapshot(id)
      .then((snapshot) => setSelectedSnapshot(snapshot))
      .catch((err) => setSnapshotError(err instanceof Error ? err.message : "Could not load that upload."))
      .finally(() => setSnapshotLoading(false));
  }, []);

  const removeUpload = useCallback(
    async (id: number) => {
      setDeleteError(null);
      try {
        await deleteUpload(id);
        setUploads((prev) => prev.filter((u) => u.id !== id));
        // Deleting the one you're currently replaying read-only has
        // nothing left to show — fall back to the live view.
        if (selectedId === id) selectUpload(null);
      } catch (err) {
        setDeleteError(err instanceof Error ? err.message : "Could not delete that upload.");
      }
    },
    [selectedId, selectUpload],
  );

  return {
    uploads,
    selectedId,
    selectedSnapshot,
    snapshotLoading,
    snapshotError,
    deleteError,
    refreshHistory,
    selectUpload,
    removeUpload,
  };
}
