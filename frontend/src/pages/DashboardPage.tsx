import { useAnalyze } from "../hooks/useAnalyze";
import UploadPanel from "../components/UploadPanel";
import ValidationBanner from "../components/ValidationBanner";
import KpiCards from "../components/KpiCards";
import CategoryDistributionChart from "../components/charts/CategoryDistributionChart";
import ThemeFrequencyChart from "../components/charts/ThemeFrequencyChart";
import SentimentDistributionChart from "../components/charts/SentimentDistributionChart";
import UrgencyBreakdownChart from "../components/charts/UrgencyBreakdownChart";
import SummaryPanel from "../components/SummaryPanel";
import FeedbackExplorer from "../components/FeedbackExplorer";

export default function DashboardPage() {
  const { status, data, error, fileName, analyze } = useAnalyze();

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-ink">Loom</h1>
        <p className="mt-1 text-sm text-ink-muted">Feedback analysis dashboard</p>
      </header>

      <UploadPanel status={status} fileName={fileName} onFile={analyze} />

      {status === "loading" && (
        <div className="mt-4 h-1 w-full overflow-hidden rounded-full bg-surface-2">
          <div className="loading-bar-fill h-full w-1/3 rounded-full bg-accent" />
        </div>
      )}

      {status === "error" && (
        <div className="mt-4 rounded-lg border border-critical/30 bg-critical/5 px-4 py-3 text-sm text-ink">
          {error}
        </div>
      )}

      {status === "success" && data && (
        <div className="mt-5 flex flex-col gap-4">
          <ValidationBanner report={data.validation_report} />
          <KpiCards analytics={data.analytics} validationReport={data.validation_report} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <CategoryDistributionChart analytics={data.analytics} />
            <ThemeFrequencyChart analytics={data.analytics} />
            <SentimentDistributionChart analytics={data.analytics} />
            <UrgencyBreakdownChart analytics={data.analytics} />
          </div>
          <SummaryPanel summary={data.summary} />
          <FeedbackExplorer items={data.items} />
        </div>
      )}
    </main>
  );
}
