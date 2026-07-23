import { useState } from "react";
import { useAnalyze } from "../hooks/useAnalyze";
import Nav from "../components/Nav";
import AmbientStatus from "../components/AmbientStatus";
import ValidationBanner from "../components/ValidationBanner";
import KpiCards from "../components/KpiCards";
import CategoryDistributionChart from "../components/charts/CategoryDistributionChart";
import ThemeFrequencyChart from "../components/charts/ThemeFrequencyChart";
import SentimentDistributionChart from "../components/charts/SentimentDistributionChart";
import UrgencyBreakdownChart from "../components/charts/UrgencyBreakdownChart";
import SummaryPanel from "../components/SummaryPanel";
import FeedbackExplorer from "../components/FeedbackExplorer";
import type { Category, Theme } from "../types/taxonomy";

const FEATURE_HIGHLIGHTS = [
  { title: "KPIs at a glance", detail: "Volume, sentiment split, top category/theme, urgency, success rate." },
  { title: "Distribution charts", detail: "Category, theme, sentiment, and urgency — click a bar to filter tickets." },
  { title: "Executive summary", detail: "A grounded narrative, generated once from the numbers already computed." },
  { title: "Feedback explorer", detail: "Search, sort, and filter every processed ticket, with full detail on expand." },
];

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

      <main className="mx-auto max-w-6xl px-6 pb-8">
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

        {status === "idle" && (
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURE_HIGHLIGHTS.map((f) => (
              <div key={f.title} className="rounded-lg border border-hairline bg-surface p-4">
                <p className="text-sm font-semibold text-ink">{f.title}</p>
                <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">{f.detail}</p>
              </div>
            ))}
          </div>
        )}

        {status === "success" && data && (
          <div className="flex flex-col gap-4">
            <ValidationBanner report={data.validation_report} />
            <KpiCards analytics={data.analytics} validationReport={data.validation_report} />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
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
            <SummaryPanel summary={data.summary} />
            <FeedbackExplorer
              items={data.items}
              categoryFilter={activeCategory}
              onCategoryFilterChange={setActiveCategory}
              themeFilter={activeTheme}
              onThemeFilterChange={setActiveTheme}
            />
          </div>
        )}
      </main>
    </div>
  );
}
