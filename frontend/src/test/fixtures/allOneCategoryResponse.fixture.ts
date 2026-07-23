/**
 * A second real POST /analyze response, captured verbatim from the live
 * local backend analyzing a 5-row all-Billing-and-Payments CSV with zero
 * skipped rows. Exercises the "single unambiguous leader" (non-tied)
 * path and a 100%-one-category/100%-negative edge case that the primary
 * fixture (which is tie-heavy) doesn't cover.
 */

import type { AnalyzeResponse } from "../../types/analyze";

export const allOneCategoryResponseFixture: AnalyzeResponse = {
  validation_report: {
    total_rows: 5,
    processed: 5,
    skipped: 0,
    skip_reasons: {},
    fell_back_count: 0,
  },
  items: [
    {
      primary_category: "Billing & Payments",
      primary_theme: "Duplicate Charge",
      sentiment: "Negative",
      sentiment_score: -0.7,
      urgency: "High",
      actionable: true,
      additional_issues: [],
      ticket_id: "1",
      feedback_text: "I was charged twice for my subscription this month please refund.",
      was_summarized: false,
    },
    {
      primary_category: "Billing & Payments",
      primary_theme: "Unexpected Charge",
      sentiment: "Negative",
      sentiment_score: -0.7,
      urgency: "High",
      actionable: true,
      additional_issues: [],
      ticket_id: "2",
      feedback_text: "My credit card was billed the wrong amount for my subscription.",
      was_summarized: false,
    },
    {
      primary_category: "Billing & Payments",
      primary_theme: "Refund Delay",
      sentiment: "Negative",
      sentiment_score: -0.7,
      urgency: "Medium",
      actionable: true,
      additional_issues: [],
      ticket_id: "3",
      feedback_text: "I never got my refund for the cancelled subscription payment.",
      was_summarized: false,
    },
    {
      primary_category: "Billing & Payments",
      primary_theme: "Unexpected Charge",
      sentiment: "Negative",
      sentiment_score: -0.7,
      urgency: "High",
      actionable: true,
      additional_issues: [],
      ticket_id: "4",
      feedback_text: "There was an unexpected charge on my card for a service I did not order.",
      was_summarized: false,
    },
    {
      primary_category: "Billing & Payments",
      primary_theme: "Subscription/Renewal Issue",
      sentiment: "Negative",
      sentiment_score: -0.6,
      urgency: "Medium",
      actionable: true,
      additional_issues: [],
      ticket_id: "5",
      feedback_text: "My subscription renewal charged me at the old price by mistake, please fix billing.",
      was_summarized: false,
    },
  ],
  analytics: {
    total_uploaded: 5,
    total_processed: 5,
    total_skipped: 0,
    skip_reasons: {},
    processing_success_rate: 100,
    category_distribution: { "Billing & Payments": 5 },
    category_distribution_pct: { "Billing & Payments": 100 },
    theme_frequency: {
      "Duplicate Charge": 1,
      "Unexpected Charge": 2,
      "Refund Delay": 1,
      "Subscription/Renewal Issue": 1,
    },
    theme_sentiment_avg: {
      "Duplicate Charge": -0.7,
      "Unexpected Charge": -0.7,
      "Refund Delay": -0.7,
      "Subscription/Renewal Issue": -0.6,
    },
    sentiment_distribution: { Negative: 5 },
    sentiment_distribution_pct: { Negative: 100 },
    urgency_distribution: { High: 3, Medium: 2 },
    urgency_rollup_with_additional_issues: { High: 3, Medium: 2 },
    high_urgency_count: 3,
    actionable_count: 5,
    actionable_pct: 100,
    fell_back_count: 0,
    top_category: "Billing & Payments",
    category_leaders: ["Billing & Payments"],
    top_theme: "Unexpected Charge",
    theme_leaders: ["Unexpected Charge"],
    top_categories: ["Billing & Payments"],
    top_themes: ["Unexpected Charge", "Duplicate Charge", "Refund Delay"],
  },
  summary:
    "The customer feedback indicates a strong focus on issues related to Billing & Payments, which accounts for 100% of the processed feedback. The most prominent theme driving this feedback is Unexpected Charge, which, along with Duplicate Charge and Refund Delay, highlights significant concerns among customers. Notably, all feedback carries a negative sentiment, with a total of 5 responses categorized as negative. There is a sense of urgency present, with 3 issues marked as high urgency, signaling an immediate need for attention and resolution. Despite the challenges reflected in the feedback, the processing success rate stands at 100%, indicating that all submissions were handled effectively.",
};
