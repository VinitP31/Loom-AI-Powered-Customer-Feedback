/**
 * Single source of truth for every color used in charts and the table.
 * frontend/CLAUDE.md: "Use the SAME color for the same value across every
 * chart and the table" — every component imports from here, never
 * hardcodes a hex value for a category/sentiment/urgency.
 *
 * Categorical hues are assigned in FIXED enum order (never cycled/sorted
 * by count) and were validated colorblind-safe with the dataviz skill's
 * validate_palette.js (CVD-safe adjacent pairs, contrast on light/dark
 * surfaces). "Other" always gets the neutral gray, per convention.
 */

import type { Category, Sentiment, Urgency } from "../types/taxonomy";

export const SENTIMENT_COLOR: Record<Sentiment, string> = {
  Positive: "#0ca30c",
  Neutral: "#8b93a1",
  Negative: "#d03b3b",
};

export const URGENCY_COLOR: Record<Urgency, string> = {
  High: "#d03b3b",
  Medium: "#b3790f",
  Low: "#8b93a1",
};

export const CATEGORY_COLOR: Record<Category, string> = {
  "Billing & Payments": "#2a78d6",
  "Account & Access": "#1baf7a",
  "Performance & Reliability": "#eda100",
  "Functional Issues": "#eb6834",
  "Feature Requests & Enhancements": "#008300",
  "Usability & User Experience": "#4a3aa7",
  "Support Experience": "#e87ba4",
  Security: "#e34948",
  Other: "#a7adb8",
};

/** Sort order used to rank urgency (High first) and sentiment (Negative
 * first) wherever a fixed severity ordering matters more than alphabetical
 * or count order — e.g. table sort, legend order. */
export const URGENCY_RANK: Record<Urgency, number> = { High: 3, Medium: 2, Low: 1 };
export const SENTIMENT_RANK: Record<Sentiment, number> = { Negative: 1, Neutral: 2, Positive: 3 };
