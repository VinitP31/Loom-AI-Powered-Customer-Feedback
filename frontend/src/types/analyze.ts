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
  primary_category: Category;
  primary_theme: Theme;
  sentiment: Sentiment;
  sentiment_score: number;
  urgency: Urgency;
  actionable: boolean;
  additional_issues: AdditionalIssue[];
}

export interface ValidationReport {
  total_rows: number;
  processed: number;
  skipped: number;
  skip_reasons: Record<string, number>;
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

export interface AnalyzeResponse {
  validation_report: ValidationReport;
  items: TicketClassification[];
  analytics: Analytics;
  summary: string;
}

/** Structured shape of a 4xxx file-validation error response body,
 * e.g. { "error_code": 4001, "message": "missing required 'feedback' column" }. */
export interface ApiErrorDetail {
  error_code: number;
  message: string;
}
