/**
 * Owns the chat widget's open/closed state, conversation history, and
 * in-flight question. One conversation per mount (DashboardPage remounts
 * nothing on upload/history-navigation, so switching what "this
 * dashboard" scope points at just changes future questions' snapshot_id,
 * never clears past messages — same "don't lose what's on screen"
 * instinct as the rest of the app).
 */

import { useCallback, useState } from "react";
import { sendChatMessage } from "../api/chatClient";
import type { ChatScope, ChatSource } from "../types/chat";

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
}

export interface UseChatState {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  scope: ChatScope;
  setScope: (scope: ChatScope) => void;
  messages: ChatMessage[];
  isSending: boolean;
  error: string | null;
  ask: (question: string) => Promise<void>;
}

export function useChat(dashboardSnapshotId: number | null): UseChatState {
  const [isOpen, setIsOpen] = useState(false);
  const [scope, setScope] = useState<ChatScope>("dashboard");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isSending) return;

      setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
      setIsSending(true);
      setError(null);
      try {
        // scope="all" ignores whatever "this dashboard" currently points
        // at — send null explicitly rather than relying on the backend
        // to ignore a stray snapshot_id.
        const response = await sendChatMessage(trimmed, scope, scope === "dashboard" ? dashboardSnapshotId : null);
        setMessages((prev) => [...prev, { role: "assistant", text: response.answer, sources: response.sources }]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not reach the chat backend.");
      } finally {
        setIsSending(false);
      }
    },
    [scope, dashboardSnapshotId, isSending],
  );

  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
    scope,
    setScope,
    messages,
    isSending,
    error,
    ask,
  };
}
