import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "./DashboardPage";
import { allOneCategoryResponseFixture } from "../test/fixtures/allOneCategoryResponse.fixture";

async function uploadFile(fileName: string) {
  const file = new File(["id,feedback\n1,test"], fileName, { type: "text/csv" });
  const input = screen.getByLabelText(/upload file/i, { selector: "input" }) as HTMLInputElement;
  await userEvent.upload(input, file);
}

describe("DashboardPage — edge cases", () => {
  it("renders a single unambiguous leader (no tie) for an all-one-category, all-negative batch", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => allOneCategoryResponseFixture }),
    );

    render(<DashboardPage />);
    await uploadFile("one_category.csv");

    await waitFor(() => {
      expect(screen.getAllByText("Billing & Payments").length).toBeGreaterThan(0);
    });

    // top_category/top_theme are non-null here — no "Tied:" tag should render.
    expect(screen.queryByText(/tied:/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Unexpected Charge").length).toBeGreaterThan(0);

    // 100% negative, 0% positive — must not crash on a missing Positive key.
    expect(screen.getByText("0.0%")).toBeInTheDocument();
    expect(screen.getAllByText("100.0%").length).toBeGreaterThan(0);

    // A single-bar category chart still renders without breaking layout.
    expect(screen.getByText("Category Distribution")).toBeInTheDocument();
  });

  it("shows the backend's 4003 message when every row is skipped (file-level rejection, not a success payload)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({
          detail: { error_code: 4003, message: "no valid feedback found after row validation" },
        }),
      }),
    );

    render(<DashboardPage />);
    await uploadFile("all_empty.csv");

    await waitFor(() => {
      expect(screen.getByText(/no valid feedback found after row validation/i)).toBeInTheDocument();
    });
  });
});
