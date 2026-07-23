/**
 * Owns the entire upload -> analyze -> render lifecycle in one place:
 * request status, the uploaded file, and the response payload
 * (frontend/CLAUDE.md, "State handling"). No global store, no
 * persistence, no re-fetch — a new upload just replaces the payload.
 */

import { useCallback, useState } from "react";
import { analyzeCsv, AnalyzeApiError } from "../api/analyzeClient";
import type { AnalyzeResponse } from "../types/analyze";

export type AnalyzeStatus = "idle" | "loading" | "success" | "error";

export interface UseAnalyzeState {
  status: AnalyzeStatus;
  data: AnalyzeResponse | null;
  error: string | null;
  fileName: string | null;
  analyze: (file: File) => Promise<void>;
  reset: () => void;
}

export function useAnalyze(): UseAnalyzeState {
  const [status, setStatus] = useState<AnalyzeStatus>("idle");
  const [data, setData] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const analyze = useCallback(async (file: File) => {
    setStatus("loading");
    setError(null);
    setFileName(file.name);
    try {
      const result = await analyzeCsv(file);
      setData(result);
      setStatus("success");
    } catch (err) {
      const message =
        err instanceof AnalyzeApiError ? err.message : "Something went wrong analyzing this file.";
      setError(message);
      setData(null);
      setStatus("error");
    }
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setData(null);
    setError(null);
    setFileName(null);
  }, []);

  return { status, data, error, fileName, analyze, reset };
}
