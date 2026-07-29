/**
 * Typed client for POST /chat — the RAG "chat with tickets" widget.
 * Separate concern from analyzeClient.ts's single /analyze call (see
 * golden rule 2): a query against already-persisted tickets, same class
 * of allowed extra call as the history endpoints in uploadsClient.ts.
 */

import type { ChatResponse, ChatScope } from "../types/chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

/** `snapshotId` is sent as-is — the caller (useChat) is responsible for
 * passing null when `scope` is "all", not this client. */
export async function sendChatMessage(
  question: string,
  scope: ChatScope,
  snapshotId: number | null,
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, scope, snapshot_id: snapshotId }),
  });

  if (!response.ok) {
    let message = `Chat request failed (HTTP ${response.status}).`;
    try {
      const body = await response.json();
      if (body?.detail) message = typeof body.detail === "string" ? body.detail : message;
    } catch {
      // Response body wasn't JSON — fall back to the generic message above.
    }
    throw new Error(message);
  }

  return (await response.json()) as ChatResponse;
}
