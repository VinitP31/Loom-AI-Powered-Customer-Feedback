/**
 * Full POST /analyze response contract — mirrors
 * backend/api/response_models.py + backend/analytics/aggregate.py exactly.
 * The frontend renders directly from this shape; nothing here is
 * recomputed client-side (frontend/CLAUDE.md, golden rule 4).
 */

import type { Category, Sentiment, Theme, Urgency } from "./taxonomy";

export interface AdditionalIssue {
  category: Category;
  theme: Theme;
  urgency: Urgency;
}

export interface TicketClassification {
  ticket_id: string;
  feedback_text: string;
  was_summarized: boolean;
  /** Row-level quality flags from validate.py — e.g. "html_present",
   * "markdown_present", "duplicate_feedback", "long_ticket". Never
   * produced or seen by the model. */
  warnings: string[];
  primary_category: Category;
  primary_theme: Theme;
  sentiment: Sentiment;
  sentiment_score: number;
  urgency: Urgency;
  actionable: boolean;
  additional_issues: AdditionalIssue[];
}

export interface SkippedRow {
  ticket_id: string;
  reason: string;
}

export interface ValidationReport {
  total_rows: number;
  processed: number;
  skipped: number;
  skip_reasons: Record<string, number>;
  skipped_rows: SkippedRow[];
  fell_back_count: number;
}

/**
 * Backend keys these count/percentage dicts by whatever category/theme
 * strings are actually present in the batch — never assume every
 * enum member is present. Partial<Record<...>> models that: unseen keys
 * are simply absent, not zero.
 */
export interface Analytics {
  total_uploaded: number;
  total_processed: number;
  total_skipped: number;
  skip_reasons: Record<string, number>;
  processing_success_rate: number;

  category_distribution: Partial<Record<Category, number>>;
  category_distribution_pct: Partial<Record<Category, number>>;

  theme_frequency: Partial<Record<Theme, number>>;
  theme_sentiment_avg: Partial<Record<Theme, number>>;

  sentiment_distribution: Partial<Record<Sentiment, number>>;
  sentiment_distribution_pct: Partial<Record<Sentiment, number>>;

  urgency_distribution: Partial<Record<Urgency, number>>;
  /** Primary + additional_issues urgency, kept separate from
   * urgency_distribution to avoid double-counting a ticket. Label any
   * chart built from this as including secondary issues explicitly. */
  urgency_rollup_with_additional_issues: Partial<Record<Urgency, number>>;

  high_urgency_count: number;
  actionable_count: number;
  actionable_pct: number;
  fell_back_count: number;

  /** null on a tie — render category_leaders instead. Never assume
   * non-null. */
  top_category: Category | null;
  category_leaders: Category[];
  /** null on a tie — render theme_leaders instead. Never assume
   * non-null. */
  top_theme: Theme | null;
  theme_leaders: Theme[];

  top_categories: Category[];
  top_themes: Theme[];
}

/**
 * Week-over-week diff against the previous upload — pure Python-computed
 * (backend/storage/compare.py), never recomputed here. Keyed dicts follow
 * the same "only present keys, never assume every enum member" rule as
 * Analytics above. Percentage-point deltas (sentiment/category) and
 * count deltas (urgency) can be positive, negative, or zero.
 */
export interface Comparison {
  previous_uploaded_at: string;
  sentiment_shift_pct: Partial<Record<Sentiment, number>>;
  sentiment_pct_before: Partial<Record<Sentiment, number>>;
  sentiment_pct_after: Partial<Record<Sentiment, number>>;
  category_shift_pct: Partial<Record<Category, number>>;
  urgency_shift_count: Partial<Record<Urgency, number>>;
  urgency_count_before: Partial<Record<Urgency, number>>;
  urgency_count_after: Partial<Record<Urgency, number>>;
  new_themes: Theme[];
  disappeared_themes: Theme[];
  high_urgency_count_delta: number;
  high_urgency_count_before: number;
  high_urgency_count_after: number;
  actionable_pct_delta: number;
  actionable_pct_before: number;
  actionable_pct_after: number;
  fell_back_count_delta: number;
  fell_back_count_before: number;
  fell_back_count_after: number;
}

export interface AnalyzeResponse {
  validation_report: ValidationReport;
  items: TicketClassification[];
  analytics: Analytics;
  summary: string;
  /** Row id in the `analysis_snapshots` table this upload was saved as. */
  upload_id: number;
  uploaded_at: string;
  /** null on the first-ever upload — nothing to compare against yet. */
  comparison: Comparison | null;
}

/** GET /uploads — one entry per past upload, newest first. */
export interface UploadSummary {
  id: number;
  uploaded_at: string;
  source_filename: string;
}

/**
 * GET /uploads/{id} — a past upload's own dashboard, replayed read-only.
 * Includes `items` (storage/ticket_items — one row per ticket, persisted
 * alongside the aggregate snapshot), so the FeedbackExplorer table works
 * on history replay too, same as the live dashboard.
 */
export interface HistoricalSnapshot {
  id: number;
  uploaded_at: string;
  source_filename: string;
  validation_report: ValidationReport;
  items: TicketClassification[];
  analytics: Analytics;
  summary: string;
  /** The diff AS COMPUTED at the time this upload was saved (vs whatever
   * was "latest" back then) — persisted, not recomputed against today's
   * latest upload. null on the first-ever upload. */
  comparison: Comparison | null;
}

/** Structured shape of a 4xxx file-validation error response body,
 * e.g. { "error_code": 4001, "message": "missing required 'feedback' column" }. */
export interface ApiErrorDetail {
  error_code: number;
  message: string;
}
