/**
 * Regression test for "clicking a category/theme bar filters the ticket
 * table" — the specific behavior a plain fetch-mock test can't verify,
 * since it requires the chart to actually render as SVG and be clicked.
 * jsdom has no layout engine and no ResizeObserver, so
 * src/test/setup.ts stubs both (see comments there) to make Recharts
 * render real, clickable bars instead of an empty container.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "./DashboardPage";
import { analyzeResponseFixture } from "../test/fixtures/analyzeResponse.fixture";

async function uploadFile() {
  const file = new File(["id,feedback\n1,test"], "mini_test.csv", { type: "text/csv" });
  const input = screen.getByLabelText(/choose file/i, { selector: "input" }) as HTMLInputElement;
  await userEvent.upload(input, file);
}

describe("DashboardPage — chart click-to-filter", () => {
  it("clicking a category bar filters the Feedback Explorer to only that category's tickets", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => analyzeResponseFixture }));

    const { container } = render(<DashboardPage />);
    await uploadFile();

    await waitFor(() => {
      expect(screen.getByText("Category Distribution")).toBeInTheDocument();
    });

    // All 3 tickets (one per category) visible before filtering.
    expect(screen.getByText("I was charged twice for my subscription this month please refund.")).toBeInTheDocument();
    expect(screen.getByText("App keeps crashing every time I open the camera screen.")).toBeInTheDocument();
    expect(screen.getByText("Great job on the new dashboard redesign, much easier to use now!")).toBeInTheDocument();

    // Category Distribution is the first chart in DOM order. All three
    // categories here are tied at count 1, so the bar order isn't
    // alphabetical — find the y-axis tick labeled "Billing & Payments"
    // and click the bar-rectangle at that SAME index (ticks and bars are
    // rendered from the same ordered data array, one-to-one). Re-queried
    // fresh each click since a state update re-renders the SVG and
    // detaches the previous nodes.
    function findBillingBar(): SVGPathElement {
      const ticks = Array.from(container.querySelectorAll(".recharts-yAxis-tick-labels tspan"));
      const tickIndex = ticks.findIndex((el) => el.textContent === "Billing & Payments");
      expect(tickIndex).toBeGreaterThanOrEqual(0);
      const chartRoot = ticks[tickIndex].closest(".recharts-wrapper")!;
      const bar = chartRoot.querySelectorAll(".recharts-bar-rectangle path")[tickIndex];
      expect(bar).toBeTruthy();
      return bar as SVGPathElement;
    }

    await userEvent.click(findBillingBar());

    // Table narrows to the one Billing & Payments ticket...
    expect(screen.getByText("I was charged twice for my subscription this month please refund.")).toBeInTheDocument();
    // ...and the other two categories' tickets drop out.
    expect(screen.queryByText("App keeps crashing every time I open the camera screen.")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Great job on the new dashboard redesign, much easier to use now!"),
    ).not.toBeInTheDocument();

    // An active-filter pill names the filter, and the category dropdown
    // (in the Feedback Explorer's own filter row) reflects the same state.
    expect(screen.getByText("Category: Billing & Payments")).toBeInTheDocument();

    // Clicking the same bar again clears the filter.
    await userEvent.click(findBillingBar());
    expect(screen.getByText("App keeps crashing every time I open the camera screen.")).toBeInTheDocument();
    expect(screen.queryByText("Category: Billing & Payments")).not.toBeInTheDocument();
  });
});
