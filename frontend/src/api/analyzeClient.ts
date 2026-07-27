/**
 * Typed client for the single POST /analyze call. This is the ONLY
 * backend endpoint the frontend ever calls (frontend/CLAUDE.md, golden
 * rule 2) — no /upload, no polling, no upload_id. A successful response
 * streams NDJSON (one request, one response, still — the stream only
 * exists for this call's lifetime): zero or more progress lines followed
 * by exactly one result line, so real per-ticket progress is available
 * without a second endpoint or any server-side job state.
 */

import type { AnalyzeResponse, ApiErrorDetail } from "../types/analyze";

export interface AnalyzeProgress {
  stage: "classifying" | "summarizing";
  done: number;
  total: number;
}

// Overridable via .env (VITE_API_BASE_URL) for non-local deployments;
// defaults to the backend's documented local dev address (backend/README.md).
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

/** Thrown on any non-2xx /analyze response. Carries the backend's
 * error_code (4001/4002/4003, see backend/CLAUDE.md) when the server sent
 * one, so the UI can show a precise, actionable message. */
export class AnalyzeApiError extends Error {
  readonly errorCode?: number;
  readonly status: number;

  constructor(message: string, status: number, errorCode?: number) {
    super(message);
    this.name = "AnalyzeApiError";
    this.status = status;
    this.errorCode = errorCode;
  }
}

export async function analyzeCsv(
  file: File,
  onProgress?: (progress: AnalyzeProgress) => void,
): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/analyze`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new AnalyzeApiError(
      "Could not reach the Loom backend. Make sure the API server is running and reachable.",
      0,
    );
  }

  if (!response.ok) {
    let detail: ApiErrorDetail | undefined;
    try {
      const body = await response.json();
      detail = body?.detail as ApiErrorDetail | undefined;
    } catch {
      // Response body wasn't JSON — fall through to the generic message below.
    }
    throw new AnalyzeApiError(
      detail?.message ?? `Analysis failed (HTTP ${response.status}).`,
      response.status,
      detail?.error_code,
    );
  }

  if (!response.body) {
    // No streaming body reader available (shouldn't happen for a real
    // fetch Response) — fall back to the old whole-body parse.
    return (await response.json()) as AnalyzeResponse;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: AnalyzeResponse | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? ""; // last element may be a partial line — keep it for the next chunk

    for (const line of lines) {
      if (!line.trim()) continue;
      const event = JSON.parse(line);
      if (event.type === "progress") {
        onProgress?.({ stage: event.stage, done: event.done, total: event.total });
      } else if (event.type === "result") {
        result = event.data as AnalyzeResponse;
      }
    }
  }

  if (!result) {
    throw new AnalyzeApiError("Analysis stream ended without a result.", response.status);
  }
  return result;
}
