import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ExportButton from "./ExportButton";
import { analyzeResponseFixture } from "../test/fixtures/analyzeResponse.fixture";
import * as exportReport from "../utils/exportReport";

describe("ExportButton", () => {
  it("triggers the PDF exporter with the current data + file name", async () => {
    const pdfSpy = vi.spyOn(exportReport, "exportReportPdf").mockImplementation(() => {});
    render(<ExportButton data={analyzeResponseFixture} fileName="mini_test.csv" />);

    await userEvent.click(screen.getByText("Export PDF"));

    expect(pdfSpy).toHaveBeenCalledWith(analyzeResponseFixture, "mini_test.csv");
  });
});
