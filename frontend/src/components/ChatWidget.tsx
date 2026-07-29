/**
 * "Chat with tickets" — the Morphing Orb widget (see the chat-widget
 * design review artifact). A gradient orb sits fixed bottom-right,
 * gently pulsing while idle; clicking it morphs the circle into a chat
 * panel rather than just fading one in. Only ever rendered while a
 * dashboard (live or historical replay) is on screen — same visibility
 * rule as the History toggle, never on the idle landing page.
 *
 * `dashboardSnapshotId` is whichever upload id is "this dashboard" right
 * now (the live upload's id, or the replayed snapshot's id) — required
 * for scope="dashboard" questions; scope="all" ignores it entirely.
 */

import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { useChat } from "../hooks/useChat";
import type { ChatScope } from "../types/chat";

interface ChatWidgetProps {
  dashboardSnapshotId: number | null;
}

const SPARKLE_ICON = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2Z" fill="currentColor" />
  </svg>
);

export default function ChatWidget({ dashboardSnapshotId }: ChatWidgetProps) {
  const { isOpen, open, close, scope, setScope, messages, isSending, error, ask } = useChat(dashboardSnapshotId);
  const [draft, setDraft] = useState("");
  const msgsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = msgsRef.current;
    // jsdom (unit tests) doesn't implement scrollTo on elements — guard
    // rather than let a real browser API silently be unavailable in tests.
    if (node?.scrollTo) node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [messages, isSending]);

  function handleSend() {
    if (!draft.trim() || isSending) return;
    void ask(draft);
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") handleSend();
  }

  function handleScopeClick(next: ChatScope) {
    if (next === "dashboard" && dashboardSnapshotId === null) return;
    setScope(next);
  }

  return (
    <div className="fixed right-6 bottom-6 z-40 flex flex-col items-end">
      {isOpen && (
        <div
          role="dialog"
          aria-label="Chat with tickets"
          className="chat-orb-window mb-4 flex h-[440px] w-[330px] flex-col overflow-hidden rounded-[20px] bg-surface shadow-[0_16px_40px_rgba(30,20,90,0.22),0_4px_12px_rgba(30,20,90,0.14)]"
        >
          <div className="flex items-center gap-2 bg-gradient-to-r from-accent to-accent px-4 py-3 font-bold text-accent-ink">
            <span className="chat-orb-live-dot h-[7px] w-[7px] rounded-full bg-[#6fe08a]" />
            <span className="flex-1 text-[13.5px]">Chat with tickets</span>
            <button
              type="button"
              onClick={close}
              aria-label="Close chat"
              className="flex h-[22px] w-[22px] items-center justify-center rounded-full bg-white/20 text-sm leading-none"
            >
              &times;
            </button>
          </div>

          <div className="flex gap-1.5 border-b border-hairline px-3.5 py-2.5">
            <button
              type="button"
              onClick={() => handleScopeClick("dashboard")}
              disabled={dashboardSnapshotId === null}
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${
                scope === "dashboard" ? "bg-accent/15 text-accent" : "bg-surface-2 text-ink-muted"
              }`}
            >
              This dashboard
            </button>
            <button
              type="button"
              onClick={() => handleScopeClick("all")}
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                scope === "all" ? "bg-accent/15 text-accent" : "bg-surface-2 text-ink-muted"
              }`}
            >
              All history
            </button>
          </div>

          <div ref={msgsRef} className="flex flex-1 flex-col gap-2.5 overflow-y-auto px-3.5 py-3">
            {messages.length === 0 && !isSending && (
              <p className="text-xs text-ink-muted">
                Ask about {scope === "dashboard" ? "this upload's" : "every uploaded"} tickets — e.g. "who's having
                login trouble?" or "any billing complaints?"
              </p>
            )}
            {messages.map((message, index) => (
              <div
                key={index}
                className={`chat-orb-msg-in max-w-[85%] rounded-xl px-2.5 py-2 text-[12.5px] leading-snug ${
                  message.role === "user"
                    ? "self-end rounded-br-[3px] bg-accent text-accent-ink"
                    : "self-start rounded-bl-[3px] bg-surface-2 text-ink"
                }`}
              >
                {message.text}
                {message.sources && message.sources.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {message.sources.map((source) => (
                      <span
                        key={`${source.snapshot_id}-${source.ticket_id}`}
                        className="rounded-full bg-accent/12 px-2 py-0.5 text-[10.5px] font-bold text-accent tabular-nums"
                        title={`${source.source_filename} · similarity ${source.similarity.toFixed(2)}`}
                      >
                        {source.ticket_id}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {isSending && (
              <div className="chat-orb-typing self-start flex gap-1 rounded-xl bg-surface-2 px-3 py-2.5">
                <i className="chat-orb-typing-dot h-1.5 w-1.5 rounded-full bg-ink-muted" style={{ animationDelay: "0ms" }} />
                <i className="chat-orb-typing-dot h-1.5 w-1.5 rounded-full bg-ink-muted" style={{ animationDelay: "150ms" }} />
                <i className="chat-orb-typing-dot h-1.5 w-1.5 rounded-full bg-ink-muted" style={{ animationDelay: "300ms" }} />
              </div>
            )}
            {error && <p className="text-xs text-critical">{error}</p>}
          </div>

          <div className="flex gap-2 border-t border-hairline p-2.5">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about these tickets…"
              className="flex-1 rounded-full border border-hairline bg-surface-2 px-3 py-2 text-xs text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={!draft.trim() || isSending}
              aria-label="Send"
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink disabled:opacity-40"
            >
              ➤
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={isOpen ? close : open}
        aria-label={isOpen ? "Close chat with tickets" : "Chat with tickets"}
        aria-expanded={isOpen}
        className="chat-orb-btn flex h-[58px] w-[58px] items-center justify-center rounded-full text-accent-ink"
      >
        {SPARKLE_ICON}
      </button>
    </div>
  );
}
