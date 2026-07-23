/**
 * The idle (pre-upload) screen. Replaces the old four generic
 * description cards with: a hero that actually acts (upload), the real
 * processing pipeline shown as steps (doubling as a data-handling trust
 * signal), and a "what you can do" capability grid. Same theme/tokens as
 * the rest of the app — this only fills the idle state with real content
 * instead of leaving it mostly blank.
 */

interface IdleLandingProps {
  onFile: (file: File) => void;
}

const PIPELINE_STEPS = [
  { title: "Upload", detail: "Drop a CSV. Only a feedback column is required." },
  { title: "Validate & redact", detail: "Bad rows are skipped and counted. PII is stripped before it reaches any model." },
  { title: "Classify", detail: "Every ticket gets a category, theme, sentiment, and urgency." },
  { title: "Explore", detail: "KPIs, charts, a written summary, and a searchable ticket table." },
];

const CAPABILITIES = [
  { title: "Click to filter", detail: "Click any category or theme bar to filter the ticket table instantly." },
  { title: "Search & sort", detail: "Full-text search over feedback, sortable by any column." },
  { title: "Drill into a ticket", detail: "Expand any row to see additional issues the model flagged." },
];

export default function IdleLanding({ onFile }: IdleLandingProps) {
  return (
    <div className="mt-2 flex flex-col gap-3">
      {/* Hero — orientation and a real action, not just a headline */}
      <div className="flex flex-col items-center rounded-lg border border-hairline bg-surface px-6 py-12 text-center">
        <p className="mb-2 text-[11.5px] font-bold uppercase tracking-wide text-accent">Get started</p>
        <h2 className="mb-3 max-w-xl text-2xl font-bold leading-tight text-ink">
          Turn a CSV of raw feedback into a stakeholder-ready dashboard.
        </h2>
        <p className="mb-6 max-w-lg text-sm leading-relaxed text-ink-2">
          Drop a CSV with a <code className="rounded bg-surface-2 px-1 py-0.5">feedback</code> column. Loom
          validates it, redacts anything personal, classifies every ticket, and hands back KPIs, charts, and a
          written summary — all from one upload.
        </p>
        <label className="mb-5 flex cursor-pointer items-center gap-2 rounded-lg bg-accent px-5 py-3 text-sm font-semibold text-accent-ink hover:brightness-110">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          Upload a CSV
          <input
            type="file"
            accept=".csv"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onFile(file);
              e.target.value = "";
            }}
          />
        </label>
        <div className="flex items-center gap-2 text-[11.5px] text-ink-muted">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="shrink-0 text-good">
            <path d="M20 6 9 17l-5-5" />
          </svg>
          Emails, phone numbers, and card numbers are redacted before anything reaches the model.
        </div>
      </div>

      {/* How it works — the real pipeline, made visible */}
      <div className="rounded-lg border border-hairline bg-surface p-5">
        <p className="mb-4 text-[11px] font-bold uppercase tracking-wide text-ink-muted">How it works</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={step.title}>
              <div className="mb-2.5 flex h-6 w-6 items-center justify-center rounded-full bg-accent text-[11px] font-bold text-accent-ink">
                {i + 1}
              </div>
              <p className="mb-1 text-[13px] font-semibold text-ink">{step.title}</p>
              <p className="text-[11.5px] leading-relaxed text-ink-muted">{step.detail}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Capabilities — outcome, not process */}
      <div className="rounded-lg border border-hairline bg-surface p-5">
        <p className="mb-4 text-[11px] font-bold uppercase tracking-wide text-ink-muted">What you'll be able to do</p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {CAPABILITIES.map((c) => (
            <div key={c.title} className="flex items-start gap-3">
              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" aria-hidden="true" />
              <div>
                <p className="text-[12.5px] font-semibold text-ink">{c.title}</p>
                <p className="text-[11px] leading-relaxed text-ink-muted">{c.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
