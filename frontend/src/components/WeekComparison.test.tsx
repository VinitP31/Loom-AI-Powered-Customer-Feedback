import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import WeekComparison from "./WeekComparison";
import type { Comparison } from "../types/analyze";

const BASE_COMPARISON: Comparison = {
  previous_uploaded_at: "2026-07-20T10:00:00+00:00",
  sentiment_shift_pct: { Positive: 56.7, Negative: -36.7, Neutral: -20 },
  sentiment_pct_before: { Positive: 10, Negative: 70, Neutral: 20 },
  sentiment_pct_after: { Positive: 66.7, Negative: 33.3, Neutral: 0 },
  category_shift_pct: {},
  urgency_shift_count: { High: -4, Medium: -2, Low: 5 },
  urgency_count_before: { High: 4, Medium: 4, Low: 2 },
  urgency_count_after: { High: 0, Medium: 2, Low: 7 },
  new_themes: ["Integration Request"],
  disappeared_themes: ["Duplicate Charge"],
  high_urgency_count_delta: -4,
  high_urgency_count_before: 4,
  high_urgency_count_after: 0,
  actionable_pct_delta: -34.4,
  actionable_pct_before: 90,
  actionable_pct_after: 55.6,
  fell_back_count_delta: 0,
  fell_back_count_before: 0,
  fell_back_count_after: 0,
};

describe("WeekComparison", () => {
  it("shows before -> after values, not a bare delta", () => {
    render(<WeekComparison comparison={BASE_COMPARISON} />);
    // "70%" (before) and "33.3%" (after) must both be on screen — a bare
    // "-36.7%" delta with no baseline is exactly what this component exists
    // to avoid.
    expect(screen.getByText("70%")).toBeInTheDocument();
    expect(screen.getByText("33.3%")).toBeInTheDocument();
  });

  it("colors a High Urgency drop as good (lower-is-better direction), not bad", () => {
    render(<WeekComparison comparison={BASE_COMPARISON} />);
    const afterValue = screen.getByText("0 tickets");
    expect(afterValue.className).toContain("text-good");
  });

  it("colors a Positive sentiment rise as good (higher-is-better direction)", () => {
    render(<WeekComparison comparison={BASE_COMPARISON} />);
    const afterValue = screen.getByText("66.7%");
    expect(afterValue.className).toContain("text-good");
  });

  it("colors an Actionable % drop as bad even though the number went down", () => {
    // Actionable dropping is NOT good news — direction is upIsGood for this
    // metric, so a negative delta must render critical, not good.
    render(<WeekComparison comparison={BASE_COMPARISON} />);
    const afterValue = screen.getByText("55.6%");
    expect(afterValue.className).toContain("text-critical");
  });

  it("renders new and resolved theme chips under the right labels", () => {
    render(<WeekComparison comparison={BASE_COMPARISON} />);
    expect(screen.getByText("First seen this week:")).toBeInTheDocument();
    expect(screen.getByText("Integration Request")).toBeInTheDocument();
    expect(screen.getByText("Not seen this week:")).toBeInTheDocument();
    expect(screen.getByText("Duplicate Charge")).toBeInTheDocument();
  });

  it("omits the theme section entirely when there are no theme changes", () => {
    render(<WeekComparison comparison={{ ...BASE_COMPARISON, new_themes: [], disappeared_themes: [] }} />);
    expect(screen.queryByText("First seen this week:")).not.toBeInTheDocument();
    expect(screen.queryByText("Not seen this week:")).not.toBeInTheDocument();
  });

  it("shows 'No change' for a zero delta instead of an arrow and a bare 0", () => {
    const noChange: Comparison = {
      ...BASE_COMPARISON,
      actionable_pct_delta: 0,
      actionable_pct_before: 50,
      actionable_pct_after: 50,
    };
    render(<WeekComparison comparison={noChange} />);
    expect(screen.getByText("No change")).toBeInTheDocument();
  });
});
