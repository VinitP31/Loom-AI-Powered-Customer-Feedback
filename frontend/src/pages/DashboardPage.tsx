import { useAnalyze } from "../hooks/useAnalyze";
import UploadPanel from "../components/UploadPanel";

export default function DashboardPage() {
  const { status, data, error, fileName, analyze } = useAnalyze();

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-ink">Loom</h1>
        <p className="mt-1 text-sm text-ink-muted">Feedback analysis dashboard</p>
      </header>

      <UploadPanel status={status} fileName={fileName} onFile={analyze} />

      {status === "error" && (
        <div className="mt-4 rounded-lg border border-critical/30 bg-critical/5 px-4 py-3 text-sm text-ink">
          {error}
        </div>
      )}

      {status === "success" && data && (
        <p className="mt-4 text-sm text-ink-2">
          Processed {data.validation_report.processed} of {data.validation_report.total_rows}{" "}
          rows ({data.validation_report.skipped} skipped).
        </p>
      )}
    </main>
  );
}
