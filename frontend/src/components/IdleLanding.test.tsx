import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import IdleLanding from "./IdleLanding";

describe("IdleLanding", () => {
  it("the hero's own upload input calls onFile with the selected file", async () => {
    const onFile = vi.fn();
    render(<IdleLanding onFile={onFile} />);

    const file = new File(["id,feedback\n1,test"], "mine.csv", { type: "text/csv" });
    const input = screen.getByLabelText(/upload a csv/i, { selector: "input" }) as HTMLInputElement;
    await userEvent.upload(input, file);

    expect(onFile).toHaveBeenCalledWith(file);
  });

  it("renders the pipeline steps and capability list", () => {
    render(<IdleLanding onFile={vi.fn()} />);
    expect(screen.getByText("Validate & redact")).toBeInTheDocument();
    expect(screen.getByText("Classify")).toBeInTheDocument();
    expect(screen.getByText("Click to filter")).toBeInTheDocument();
    expect(screen.getByText("Drill into a ticket")).toBeInTheDocument();
  });
});
