/**
 * Table of every processed ticket (items[]) with search over
 * feedback_text, sort, and filter by category/sentiment/urgency.
 * additional_issues only ever appear in a ticket's expanded row — never
 * folded into the headline distributions (frontend/CLAUDE.md, chart rule:
 * additional_issues are primary-issue-exclusive in aggregates).
 */

import { Fragment, useMemo, useState } from "react";
import type { TicketClassification } from "../types/analyze";
import type { Category, Sentiment, Theme, Urgency } from "../types/taxonomy";
import { CATEGORY_COLOR, SENTIMENT_COLOR, SENTIMENT_RANK, URGENCY_COLOR, URGENCY_RANK } from "../utils/colors";

interface FeedbackExplorerProps {
  items: TicketClassification[];
  /** Controlled by DashboardPage so a click on the category/theme charts
   * filters this table directly — "if I click Billing on the chart, I
   * want to see only Billing tickets here." */
  categoryFilter: Category | "All";
  onCategoryFilterChange: (category: Category | "All") => void;
  themeFilter: Theme | "All";
  onThemeFilterChange: (theme: Theme | "All") => void;
}

type SortKey = "ticket_id" | "primary_category" | "primary_theme" | "sentiment" | "urgency" | "actionable";

const SENTIMENT_OPTIONS: Sentiment[] = ["Positive", "Neutral", "Negative"];
const URGENCY_OPTIONS: Urgency[] = ["High", "Medium", "Low"];

export default function FeedbackExplorer({
  items,
  categoryFilter,
  onCategoryFilterChange,
  themeFilter,
  onThemeFilterChange,
}: FeedbackExplorerProps) {
  const [search, setSearch] = useState("");
  const [sentimentFilter, setSentimentFilter] = useState<Sentiment | "All">("All");
  const [urgencyFilter, setUrgencyFilter] = useState<Urgency | "All">("All");
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<1 | -1>(1);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const categories = useMemo(
    () => Array.from(new Set(items.map((i) => i.primary_category))).sort(),
    [items],
  );
  const themes = useMemo(() => Array.from(new Set(items.map((i) => i.primary_theme))).sort(), [items]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let rows = items.filter((t) => {
      if (categoryFilter !== "All" && t.primary_category !== categoryFilter) return false;
      if (themeFilter !== "All" && t.primary_theme !== themeFilter) return false;
      if (sentimentFilter !== "All" && t.sentiment !== sentimentFilter) return false;
      if (urgencyFilter !== "All" && t.urgency !== urgencyFilter) return false;
      if (q && !t.feedback_text.toLowerCase().includes(q)) return false;
      return true;
    });

    if (sortKey) {
      rows = [...rows].sort((a, b) => {
        let av: string | number = "";
        let bv: string | number = "";
        if (sortKey === "sentiment") {
          av = SENTIMENT_RANK[a.sentiment];
          bv = SENTIMENT_RANK[b.sentiment];
        } else if (sortKey === "urgency") {
          av = URGENCY_RANK[a.urgency];
          bv = URGENCY_RANK[b.urgency];
        } else if (sortKey === "actionable") {
          av = a.actionable ? 1 : 0;
          bv = b.actionable ? 1 : 0;
        } else {
          av = a[sortKey];
          bv = b[sortKey];
        }
        if (av < bv) return -1 * sortDir;
        if (av > bv) return 1 * sortDir;
        return 0;
      });
    }
    return rows;
  }, [items, search, categoryFilter, themeFilter, sentimentFilter, urgencyFilter, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 1 ? -1 : 1));
    } else {
      setSortKey(key);
      setSortDir(1);
    }
  }

  function toggleExpanded(ticketId: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(ticketId)) next.delete(ticketId);
      else next.add(ticketId);
      return next;
    });
  }

  function sortArrow(key: SortKey) {
    if (sortKey !== key) return null;
    return <span className="ml-1 text-accent">{sortDir === 1 ? "↑" : "↓"}</span>;
  }

  const hasChartFilter = categoryFilter !== "All" || themeFilter !== "All";

  return (
    <div id="feedback-explorer" className="rounded-lg border border-hairline bg-surface">
      <div className="flex flex-wrap items-center gap-2 border-b border-hairline p-4">
        <h3 className="mr-auto text-sm font-semibold text-ink">Feedback Explorer</h3>
        <input
          type="search"
          placeholder="Search feedback text…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-48 rounded-md border border-hairline bg-surface-2 px-3 py-1.5 text-xs text-ink placeholder:text-ink-muted"
        />
        <select
          value={categoryFilter}
          onChange={(e) => onCategoryFilterChange(e.target.value as Category | "All")}
          className="rounded-md border border-hairline bg-surface-2 px-2 py-1.5 text-xs text-ink"
        >
          <option value="All">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          value={themeFilter}
          onChange={(e) => onThemeFilterChange(e.target.value as Theme | "All")}
          className="rounded-md border border-hairline bg-surface-2 px-2 py-1.5 text-xs text-ink"
        >
          <option value="All">All themes</option>
          {themes.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={sentimentFilter}
          onChange={(e) => setSentimentFilter(e.target.value as Sentiment | "All")}
          className="rounded-md border border-hairline bg-surface-2 px-2 py-1.5 text-xs text-ink"
        >
          <option value="All">All sentiment</option>
          {SENTIMENT_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={urgencyFilter}
          onChange={(e) => setUrgencyFilter(e.target.value as Urgency | "All")}
          className="rounded-md border border-hairline bg-surface-2 px-2 py-1.5 text-xs text-ink"
        >
          <option value="All">All urgency</option>
          {URGENCY_OPTIONS.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </div>

      {hasChartFilter && (
        <div className="flex flex-wrap gap-2 border-b border-hairline px-4 py-2.5">
          {categoryFilter !== "All" && (
            <button
              type="button"
              onClick={() => onCategoryFilterChange("All")}
              className="inline-flex items-center gap-1.5 rounded-full bg-accent px-2.5 py-1 text-[11px] font-medium text-accent-ink"
            >
              Category: {categoryFilter}
              <span aria-hidden="true">×</span>
            </button>
          )}
          {themeFilter !== "All" && (
            <button
              type="button"
              onClick={() => onThemeFilterChange("All")}
              className="inline-flex items-center gap-1.5 rounded-full bg-accent px-2.5 py-1 text-[11px] font-medium text-accent-ink"
            >
              Theme: {themeFilter}
              <span aria-hidden="true">×</span>
            </button>
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-ink-muted">
              <th className="w-6 px-3 py-2"></th>
              <th className="cursor-pointer px-3 py-2" onClick={() => toggleSort("ticket_id")}>
                Ticket{sortArrow("ticket_id")}
              </th>
              <th className="px-3 py-2">Feedback</th>
              <th className="cursor-pointer px-3 py-2" onClick={() => toggleSort("primary_category")}>
                Category{sortArrow("primary_category")}
              </th>
              <th className="cursor-pointer px-3 py-2" onClick={() => toggleSort("primary_theme")}>
                Theme{sortArrow("primary_theme")}
              </th>
              <th className="cursor-pointer px-3 py-2" onClick={() => toggleSort("sentiment")}>
                Sentiment{sortArrow("sentiment")}
              </th>
              <th className="cursor-pointer px-3 py-2" onClick={() => toggleSort("urgency")}>
                Urgency{sortArrow("urgency")}
              </th>
              <th className="cursor-pointer px-3 py-2" onClick={() => toggleSort("actionable")}>
                Actionable{sortArrow("actionable")}
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-ink-muted">
                  No tickets match the current filters.
                </td>
              </tr>
            )}
            {filtered.map((t) => {
              const isExpanded = expanded.has(t.ticket_id);
              const isReview = t.primary_theme === "Requires Human Review";
              return (
                <Fragment key={t.ticket_id}>
                  <tr
                    className={`cursor-pointer border-t border-hairline hover:bg-surface-2 ${isReview ? "bg-accent/5" : ""}`}
                    onClick={() => toggleExpanded(t.ticket_id)}
                  >
                    <td className="px-3 py-2 text-ink-muted">{isExpanded ? "−" : "+"}</td>
                    <td className="px-3 py-2 font-mono text-ink">
                      {t.ticket_id}
                      {t.was_summarized && (
                        <span className="ml-1.5 rounded border border-hairline px-1 py-0.5 text-[9px] text-ink-muted">
                          summarized
                        </span>
                      )}
                    </td>
                    <td className="max-w-xs truncate px-3 py-2 text-ink-2">{t.feedback_text}</td>
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1.5">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ background: CATEGORY_COLOR[t.primary_category] }}
                        />
                        {t.primary_category}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-ink-2">
                      {t.primary_theme}
                      {isReview && (
                        <span className="ml-1.5 rounded-full border border-accent px-1.5 py-0.5 text-[9px] text-accent">
                          needs review
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full" style={{ background: SENTIMENT_COLOR[t.sentiment] }} />
                        {t.sentiment}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{
                          background: `${URGENCY_COLOR[t.urgency]}22`,
                          color: URGENCY_COLOR[t.urgency],
                        }}
                      >
                        {t.urgency}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-ink-2">{t.actionable ? "Yes" : "No"}</td>
                  </tr>
                  {isExpanded && (
                    <tr className="border-t border-hairline bg-surface-2">
                      <td colSpan={8} className="px-5 py-3">
                        <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-ink-muted">
                          Full feedback
                        </p>
                        <p className="mb-3 text-ink-2">{t.feedback_text}</p>
                        <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-ink-muted">
                          Additional issues
                        </p>
                        {t.additional_issues.length === 0 ? (
                          <p className="text-ink-muted">No additional issues on this ticket.</p>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {t.additional_issues.map((issue, i) => (
                              <span
                                key={i}
                                className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-surface px-2.5 py-1 text-[11px] text-ink-2"
                              >
                                <span className="h-2 w-2 rounded-full" style={{ background: URGENCY_COLOR[issue.urgency] }} />
                                {issue.category} / {issue.theme} · {issue.urgency}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
