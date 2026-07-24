import { useState } from "react";
import { useAnalyze } from "../hooks/useAnalyze";
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
import FeedbackExplorer from "../components/FeedbackExplorer";
import ExportButton from "../components/ExportButton";
import type { Category, Theme } from "../types/taxonomy";

export default function DashboardPage() {
  const { status, data, error, fileName, analyze } = useAnalyze();
  const [activeCategory, setActiveCategory] = useState<Category | "All">("All");
  const [activeTheme, setActiveTheme] = useState<Theme | "All">("All");

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

  function handleFile(file: File) {
    setActiveCategory("All");
    setActiveTheme("All");
    analyze(file);
  }

  return (
    <div>
      <Nav status={status} onFile={handleFile} />

      <main className="mx-auto max-w-[1400px] px-6 pb-8">
        <AmbientStatus status={status} fileName={fileName} onFile={handleFile} />

        {status === "loading" && (
          <div className="mb-2 h-1 w-full overflow-hidden rounded-full bg-surface-2">
            <div className="loading-bar-fill h-full w-1/3 rounded-full bg-accent" />
          </div>
        )}

        {status === "error" && (
          <div className="mb-2 rounded-lg border border-critical/30 bg-critical/5 px-4 py-3 text-sm text-ink">
            {error}
          </div>
        )}

        {status === "idle" && <IdleLanding onFile={handleFile} />}

        {status === "success" && data && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex-1">
                <ValidationBanner report={data.validation_report} />
              </div>
              <ExportButton data={data} fileName={fileName} />
            </div>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start">
              <div className="flex flex-col gap-3">
                <KpiCards analytics={data.analytics} validationReport={data.validation_report} />
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
                />
              </div>
              <div className="lg:sticky lg:top-4">
                <SummaryPanel summary={data.summary} />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
