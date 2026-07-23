/**
 * A real POST /analyze response, captured verbatim from the live local
 * backend (uvicorn on :8000) analyzing a 4-row sample CSV. Used to test
 * the frontend against the backend's actual output shape rather than a
 * hand-guessed mock.
 */

import type { AnalyzeResponse } from "../../types/analyze";

export const analyzeResponseFixture: AnalyzeResponse = {
  validation_report: {
    total_rows: 4,
    processed: 3,
    skipped: 1,
    skip_reasons: { empty_or_null_feedback: 1 },
    fell_back_count: 0,
  },
  items: [
    {
      primary_category: "Performance & Reliability",
      primary_theme: "App Crash",
      sentiment: "Negative",
      sentiment_score: -0.8,
      urgency: "High",
      actionable: true,
      additional_issues: [],
      ticket_id: "1",
      feedback_text: "App keeps crashing every time I open the camera screen.",
      was_summarized: false,
    },
    {
      primary_category: "Usability & User Experience",
      primary_theme: "Positive Feedback",
      sentiment: "Positive",
      sentiment_score: 1,
      urgency: "Low",
      actionable: false,
      additional_issues: [],
      ticket_id: "2",
      feedback_text: "Great job on the new dashboard redesign, much easier to use now!",
      was_summarized: false,
    },
    {
      primary_category: "Billing & Payments",
      primary_theme: "Duplicate Charge",
      sentiment: "Negative",
      sentiment_score: -0.7,
      urgency: "High",
      actionable: true,
      additional_issues: [],
      ticket_id: "4",
      feedback_text: "I was charged twice for my subscription this month please refund.",
      was_summarized: false,
    },
  ],
  analytics: {
    total_uploaded: 4,
    total_processed: 3,
    total_skipped: 1,
    skip_reasons: { empty_or_null_feedback: 1 },
    processing_success_rate: 75,
    category_distribution: {
      "Performance & Reliability": 1,
      "Usability & User Experience": 1,
      "Billing & Payments": 1,
    },
    category_distribution_pct: {
      "Performance & Reliability": 33.3,
      "Usability & User Experience": 33.3,
      "Billing & Payments": 33.3,
    },
    theme_frequency: { "App Crash": 1, "Positive Feedback": 1, "Duplicate Charge": 1 },
    theme_sentiment_avg: { "App Crash": -0.8, "Positive Feedback": 1, "Duplicate Charge": -0.7 },
    sentiment_distribution: { Negative: 2, Positive: 1 },
    sentiment_distribution_pct: { Negative: 66.7, Positive: 33.3 },
    urgency_distribution: { High: 2, Low: 1 },
    urgency_rollup_with_additional_issues: { High: 2, Low: 1 },
    high_urgency_count: 2,
    actionable_count: 2,
    actionable_pct: 66.7,
    fell_back_count: 0,
    top_category: null,
    category_leaders: ["Billing & Payments", "Performance & Reliability", "Usability & User Experience"],
    top_theme: null,
    theme_leaders: ["App Crash", "Duplicate Charge", "Positive Feedback"],
    top_categories: ["Performance & Reliability", "Usability & User Experience", "Billing & Payments"],
    top_themes: ["App Crash", "Positive Feedback", "Duplicate Charge"],
  },
  summary:
    "The customer feedback reveals a notable pattern of concern, with a significant portion of responses indicating high urgency issues, as evidenced by two high urgency counts out of three processed feedbacks. The feedback is evenly distributed across three categories: Billing & Payments, Performance & Reliability, and Usability & User Experience, each representing 33.3% of the total. In terms of themes, App Crash, Duplicate Charge, and Positive Feedback are tied as the top themes, highlighting both negative experiences and a positive sentiment in the feedback. However, the overall sentiment leans negative, with 66.7% of the feedback categorized as negative, suggesting an urgent need for attention to the issues raised. Despite this, there is a positive signal present, with one instance of positive feedback indicating some customer satisfaction.",
};
