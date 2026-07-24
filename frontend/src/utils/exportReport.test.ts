import { describe, expect, it } from "vitest";
import { exportReportPdf } from "./exportReport";
import { analyzeResponseFixture } from "../test/fixtures/analyzeResponse.fixture";
import { allOneCategoryResponseFixture } from "../test/fixtures/allOneCategoryResponse.fixture";

describe("exportReport", () => {
  it("exportReportPdf builds a downloadable PDF without throwing, for a tie-heavy payload", () => {
    expect(() => exportReportPdf(analyzeResponseFixture, "mini_test.csv")).not.toThrow();
  });

  it("exportReportPdf also handles a non-tied, single-category payload", () => {
    expect(() => exportReportPdf(allOneCategoryResponseFixture, null)).not.toThrow();
  });
});
