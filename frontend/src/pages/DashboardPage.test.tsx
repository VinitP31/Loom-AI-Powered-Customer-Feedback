import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "./DashboardPage";
import { analyzeResponseFixture } from "../test/fixtures/analyzeResponse.fixture";

describe("DashboardPage", () => {
  it("uploads a CSV and renders the validation banner + KPIs from a real /analyze payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => analyzeResponseFixture,
      }),
    );

    render(<DashboardPage />);

    const file = new File(["id,feedback\n1,test"], "mini_test.csv", { type: "text/csv" });
    const input = screen.getByLabelText(/choose file/i, { selector: "input" }) as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(screen.getByText("3", { selector: "strong" })).toBeInTheDocument();
    });

    // ValidationBanner: total/processed/skipped + skip reason.
    expect(screen.getByText(/empty or null feedback/i)).toBeInTheDocument();
    // KpiCards: tie handling on top_category/top_theme (no single leader in the fixture).
    expect(screen.getAllByText(/tied:/i).length).toBe(2);
    // KpiCards: backend-computed processing_success_rate rendered verbatim.
    expect(screen.getByText("75.0%")).toBeInTheDocument();

    // All four charts mount without crashing and carry a self-explanatory title.
    expect(screen.getByText("Category Distribution")).toBeInTheDocument();
    expect(screen.getByText("Top Themes")).toBeInTheDocument();
    expect(screen.getByText("Sentiment Split")).toBeInTheDocument();
    expect(screen.getByText("Urgency Breakdown")).toBeInTheDocument();

    // SummaryPanel renders the backend's executive summary verbatim.
    expect(screen.getByText(analyzeResponseFixture.summary)).toBeInTheDocument();

    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/analyze");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);

    // FeedbackExplorer: all 3 tickets render.
    expect(screen.getByText("Great job on the new dashboard redesign, much easier to use now!")).toBeInTheDocument();

    // Search narrows the table to the matching ticket only.
    await userEvent.type(screen.getByPlaceholderText(/search feedback text/i), "camera");
    expect(screen.getByText("App keeps crashing every time I open the camera screen.")).toBeInTheDocument();
    expect(screen.queryByText("Great job on the new dashboard redesign, much easier to use now!")).not.toBeInTheDocument();
    await userEvent.clear(screen.getByPlaceholderText(/search feedback text/i));

    // Expanding a row with no additional_issues shows the "none" message.
    await userEvent.click(screen.getByText("App keeps crashing every time I open the camera screen."));
    expect(screen.getByText("No additional issues on this ticket.")).toBeInTheDocument();
  });

  it("shows a readable error when the backend rejects the file", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: { error_code: 4001, message: "missing required 'feedback' column" } }),
      }),
    );

    render(<DashboardPage />);
    const file = new File(["a,b\n1,2"], "bad.csv", { type: "text/csv" });
    const input = screen.getByLabelText(/choose file/i, { selector: "input" }) as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(screen.getByText(/missing required 'feedback' column/i)).toBeInTheDocument();
    });
  });
});
