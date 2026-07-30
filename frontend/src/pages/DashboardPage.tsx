import { useEffect, useState } from "react";
import { useAnalyze } from "../hooks/useAnalyze";
import { useUploadHistory } from "../hooks/useUploadHistory";
import Nav from "../components/Nav";
import AmbientStatus from "../components/AmbientStatus";
import IdleLanding from "../components/IdleLanding";
import ValidationBanner from "../components/ValidationBanner";
import KpiCards from "../components/KpiCards";
import CategoryDistributionChart from "../components/charts/CategoryDistributionChart";
import ThemeFrequencyChart from "../components/charts/ThemeFrequencyChart";
import SentimentDistributionChart from "../components/charts/SentimentDistributionChart";
import UrgencyBreakdownChart from "../components/charts/UrgencyBreakdownChart";
import SummaryPanel from "../components/SummaryPanel";
import HeadlineSummary from "../components/HeadlineSummary";
import FeedbackExplorer from "../components/FeedbackExplorer";
import ExportButton from "../components/ExportButton";
import HistorySidebar from "../components/HistorySidebar";
import WeekComparison from "../components/WeekComparison";
import ChatWidget from "../components/ChatWidget";
import type { Category, Sentiment, Theme, Urgency } from "../types/taxonomy";

export default function DashboardPage() {
  const { status, data, error, fileName, progress, analyze } = useAnalyze();
  const {
    uploads,
    selectedId,
    selectedSnapshot,
    snapshotLoading,
    snapshotError,
    deleteError,
    refreshHistory,
    selectUpload,
    removeUpload,
  } = useUploadHistory();
  const [activeCategory, setActiveCategory] = useState<Category | "All">("All");
  const [activeTheme, setActiveTheme] = useState<Theme | "All">("All");
  const [activeSentiment, setActiveSentiment] = useState<Sentiment | "All">("All");
  const [activeUrgency, setActiveUrgency] = useState<Urgency | "All">("All");
  const [activeActionable, setActiveActionable] = useState<"All" | "Yes" | "No">("All");

  // History replay has its own independent filter state for its
  // FeedbackExplorer table — it's browsing a different dataset than the
  // live view, so it doesn't share (or reset) the live filters above.
  const [historyCategory, setHistoryCategory] = useState<Category | "All">("All");
  const [historyTheme, setHistoryTheme] = useState<Theme | "All">("All");
  const [historySentiment, setHistorySentiment] = useState<Sentiment | "All">("All");
  const [historyUrgency, setHistoryUrgency] = useState<Urgency | "All">("All");
  const [historyActionable, setHistoryActionable] = useState<"All" | "Yes" | "No">("All");

  // History is server-persisted, so the sidebar can have entries even
  // before this session uploads anything — fetch once on mount, then
  // again whenever a fresh analysis is saved (below).
  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    if (status === "success" && data) {
      refreshHistory();
      selectUpload(null); // a new upload always becomes "current" — back to the live view
    }
  }, [status, data, refreshHistory, selectUpload]);

  const [historyOpen, setHistoryOpen] = useState(false);

  const viewingHistory = selectedId !== null;
  // History is "screen 2" only — it never mounts on the idle landing screen
  // (or a loading/error state before any result exists), only once a
  // dashboard (live or replayed) is actually on screen. Even then it's
  // collapsed by default — a toggle button opens it, it never just
  // appears on its own.
  const dashboardShowing = viewingHistory || (status === "success" && !!data);
  const historyAvailable = uploads.length > 0 && dashboardShowing;
  const showSidebar = historyAvailable && historyOpen;

  // Picking a past upload from the drawer implies "keep it open" (you're
  // likely browsing several); returning to the current upload doesn't
  // force it shut, but a brand-new upload should start collapsed again.
  function handleSelectUpload(id: number | null) {
    selectUpload(id);
    if (id !== null) setHistoryOpen(true);
  }

  function scrollToExplorer() {
    document.getElementById("feedback-explorer")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function handleCategoryClick(category: Category | null) {
    setActiveCategory(category ?? "All");
    if (category) scrollToExplorer();
  }

  function handleThemeClick(theme: Theme | null) {
    setActiveTheme(theme ?? "All");
    if (theme) scrollToExplorer();
  }

  /** Shared by every KPI card that maps onto a single-value filter — one
   * click either applies that filter or clears it back to "All" if it's
   * already active, then jumps to the table so the effect is visible. */
  function handleKpiFilterClick<T>(current: T | "All", value: T, setter: (v: T | "All") => void) {
    setter(current === value ? "All" : value);
    scrollToExplorer();
  }

  function handleFile(file: File) {
    setActiveCategory("All");
    setActiveTheme("All");
    setActiveSentiment("All");
    setActiveUrgency("All");
    setActiveActionable("All");
    selectUpload(null);
    setHistoryOpen(false);
    analyze(file);
  }

  return (
    <div>
      <Nav status={status} onFile={handleFile} />

      <main className="mx-auto max-w-[1400px] px-6 pb-8">
        {/* Only occupies space while there's something to say — the
            processing animation, or an idle/error prompt. Once a result is
            showing, the dashboard itself is the status; this shouldn't
            linger above it taking up room. */}
        {status !== "success" && (
          <AmbientStatus status={status} fileName={fileName} progress={progress} onFile={handleFile} />
        )}

        {status === "loading" && (
          <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-surface-2">
            {progress ? (
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-200 ease-out"
                style={{ width: `${Math.round((progress.done / progress.total) * 100)}%` }}
              />
            ) : (
              <div className="loading-bar-fill h-full w-1/3 rounded-full bg-accent" />
            )}
          </div>
        )}

        {status === "error" && !viewingHistory && (
          <div className="mb-2 rounded-lg border border-critical/30 bg-critical/5 px-4 py-3 text-sm text-ink">
            {error}
          </div>
        )}

        {/* History only ever mounts on "screen 2" — once a dashboard (live or
            replayed) is actually showing — and even then it's collapsed
            until this toggle is clicked; it never appears on its own. */}
        {historyAvailable && (
          <button
            type="button"
            onClick={() => setHistoryOpen((open) => !open)}
            className="mb-2 flex items-center gap-2 rounded-lg border border-hairline bg-surface px-3 py-1.5 text-xs font-semibold text-ink-2 hover:bg-surface-2"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v5l3 3" />
            </svg>
            History
            <span className="text-ink-muted">({uploads.length})</span>
            <svg
              width="11"
              height="11"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`transition-transform ${historyOpen ? "rotate-180" : ""}`}
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </button>
        )}

        {deleteError && (
          <div className="mb-2 rounded-lg border border-critical/30 bg-critical/5 px-3 py-2 text-xs text-ink">
            {deleteError}
          </div>
        )}

        <div className={showSidebar ? "grid grid-cols-1 gap-3 md:grid-cols-[200px_minmax(0,1fr)] md:items-start" : ""}>
          {showSidebar && (
            <HistorySidebar
              uploads={uploads}
              selectedId={selectedId}
              currentUploadId={data?.upload_id ?? null}
              onSelect={handleSelectUpload}
              onDelete={removeUpload}
            />
          )}

          <div className="flex flex-col gap-3">
            {viewingHistory && (
              <>
                <div className="flex items-center justify-between rounded-lg border border-hairline bg-surface-2 px-3 py-2 text-xs text-ink-2">
                  <span>Viewing a past upload (read-only).</span>
                  <button
                    type="button"
                    onClick={() => selectUpload(null)}
                    className="rounded-md bg-accent px-2.5 py-1 font-semibold text-accent-ink"
                  >
                    Back to current
                  </button>
                </div>
                {snapshotLoading && <p className="text-sm text-ink-muted">Loading…</p>}
                {snapshotError && (
                  <div className="rounded-lg border border-critical/30 bg-critical/5 px-4 py-3 text-sm text-ink">
                    {snapshotError}
                  </div>
                )}
                {selectedSnapshot && (
                  <div className="flex flex-col gap-3">
                    <HeadlineSummary analytics={selectedSnapshot.analytics} validationReport={selectedSnapshot.validation_report} />
                    {selectedSnapshot.comparison && <WeekComparison comparison={selectedSnapshot.comparison} />}
                    <div className="flex justify-end">
                      <ExportButton data={selectedSnapshot} fileName={selectedSnapshot.source_filename} />
                    </div>
                    <ValidationBanner report={selectedSnapshot.validation_report} items={selectedSnapshot.items} />
                    <KpiCards
                      analytics={selectedSnapshot.analytics}
                      validationReport={selectedSnapshot.validation_report}
                      activeSentiment="All"
                      activeUrgency="All"
                      activeActionable="All"
                      activeCategory="All"
                      activeTheme="All"
                      onSentimentClick={() => {}}
                      onHighUrgencyClick={() => {}}
                      onActionableClick={() => {}}
                      onNeedsReviewClick={() => {}}
                      onTopCategoryClick={() => {}}
                      onTopThemeClick={() => {}}
                    />
                    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                      <CategoryDistributionChart analytics={selectedSnapshot.analytics} activeCategory={null} onCategoryClick={() => {}} />
                      <ThemeFrequencyChart analytics={selectedSnapshot.analytics} activeTheme={null} onThemeClick={() => {}} />
                      <SentimentDistributionChart analytics={selectedSnapshot.analytics} />
                      <UrgencyBreakdownChart analytics={selectedSnapshot.analytics} />
                    </div>
                    <FeedbackExplorer
                      items={selectedSnapshot.items}
                      categoryFilter={historyCategory}
                      onCategoryFilterChange={setHistoryCategory}
                      themeFilter={historyTheme}
                      onThemeFilterChange={setHistoryTheme}
                      sentimentFilter={historySentiment}
                      onSentimentFilterChange={setHistorySentiment}
                      urgencyFilter={historyUrgency}
                      onUrgencyFilterChange={setHistoryUrgency}
                      actionableFilter={historyActionable}
                      onActionableFilterChange={setHistoryActionable}
                    />
                    <SummaryPanel summary={selectedSnapshot.summary} />
                  </div>
                )}
              </>
            )}

            {!viewingHistory && status === "idle" && <IdleLanding onFile={handleFile} />}

            {!viewingHistory && status === "success" && data && (
          <div className="flex flex-col gap-3">
            <HeadlineSummary analytics={data.analytics} validationReport={data.validation_report} />
            {data.comparison && <WeekComparison comparison={data.comparison} />}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex-1">
                <ValidationBanner report={data.validation_report} items={data.items} />
              </div>
              <ExportButton data={data} fileName={fileName} />
            </div>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start">
              <div className="flex flex-col gap-3">
                <KpiCards
                  analytics={data.analytics}
                  validationReport={data.validation_report}
                  activeSentiment={activeSentiment}
                  activeUrgency={activeUrgency}
                  activeActionable={activeActionable}
                  activeCategory={activeCategory}
                  activeTheme={activeTheme}
                  onSentimentClick={(s) => handleKpiFilterClick(activeSentiment, s, setActiveSentiment)}
                  onHighUrgencyClick={() => handleKpiFilterClick(activeUrgency, "High" as Urgency, setActiveUrgency)}
                  onActionableClick={() => handleKpiFilterClick(activeActionable, "Yes", setActiveActionable)}
                  onNeedsReviewClick={() => handleThemeClick(activeTheme === "Requires Human Review" ? null : "Requires Human Review")}
                  onTopCategoryClick={(c) => handleCategoryClick(activeCategory === c ? null : c)}
                  onTopThemeClick={(t) => handleThemeClick(activeTheme === t ? null : t)}
                />
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  <CategoryDistributionChart
                    analytics={data.analytics}
                    activeCategory={activeCategory === "All" ? null : activeCategory}
                    onCategoryClick={handleCategoryClick}
                  />
                  <ThemeFrequencyChart
                    analytics={data.analytics}
                    activeTheme={activeTheme === "All" ? null : activeTheme}
                    onThemeClick={handleThemeClick}
                  />
                  <SentimentDistributionChart analytics={data.analytics} />
                  <UrgencyBreakdownChart analytics={data.analytics} />
                </div>
                <FeedbackExplorer
                  items={data.items}
                  categoryFilter={activeCategory}
                  onCategoryFilterChange={setActiveCategory}
                  themeFilter={activeTheme}
                  onThemeFilterChange={setActiveTheme}
                  sentimentFilter={activeSentiment}
                  onSentimentFilterChange={setActiveSentiment}
                  urgencyFilter={activeUrgency}
                  onUrgencyFilterChange={setActiveUrgency}
                  actionableFilter={activeActionable}
                  onActionableFilterChange={setActiveActionable}
                />
              </div>
              <div className="lg:sticky lg:top-4">
                <SummaryPanel summary={data.summary} />
              </div>
            </div>
          </div>
            )}
          </div>
        </div>
      </main>
      {dashboardShowing && (
        <ChatWidget dashboardSnapshotId={viewingHistory ? (selectedSnapshot?.id ?? null) : (data?.upload_id ?? null)} />
      )}
    </div>
  );
}
