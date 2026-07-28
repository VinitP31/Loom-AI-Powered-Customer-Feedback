import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import HistorySidebar from "./HistorySidebar";
import type { UploadSummary } from "../types/analyze";

const UPLOADS: UploadSummary[] = [
  { id: 2, uploaded_at: "2026-07-28T12:16:00+00:00", source_filename: "loom_dev_10_week2.csv" },
  { id: 1, uploaded_at: "2026-07-28T12:15:00+00:00", source_filename: "loom_dev_10.csv" },
];

describe("HistorySidebar", () => {
  it("renders nothing when there are no uploads", () => {
    const { container } = render(
      <HistorySidebar uploads={[]} selectedId={null} currentUploadId={null} onSelect={vi.fn()} onDelete={vi.fn()} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("lists every upload by filename and marks the current one", () => {
    render(
      <HistorySidebar uploads={UPLOADS} selectedId={null} currentUploadId={2} onSelect={vi.fn()} onDelete={vi.fn()} />,
    );
    expect(screen.getByText("loom_dev_10_week2.csv")).toBeInTheDocument();
    expect(screen.getByText("loom_dev_10.csv")).toBeInTheDocument();
    expect(screen.getByText(/· Current/)).toBeInTheDocument();
  });

  it("clicking a non-current entry selects it", async () => {
    const onSelect = vi.fn();
    render(
      <HistorySidebar uploads={UPLOADS} selectedId={null} currentUploadId={2} onSelect={onSelect} onDelete={vi.fn()} />,
    );
    await userEvent.click(screen.getByText("loom_dev_10.csv"));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("clicking the current entry again passes null (back to live view)", async () => {
    const onSelect = vi.fn();
    render(
      <HistorySidebar uploads={UPLOADS} selectedId={null} currentUploadId={2} onSelect={onSelect} onDelete={vi.fn()} />,
    );
    await userEvent.click(screen.getByText("loom_dev_10_week2.csv"));
    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("Enter key on a focused row selects it, same as a click", async () => {
    const onSelect = vi.fn();
    render(
      <HistorySidebar uploads={UPLOADS} selectedId={null} currentUploadId={2} onSelect={onSelect} onDelete={vi.fn()} />,
    );
    const row = screen.getByText("loom_dev_10.csv").closest('[role="button"]') as HTMLElement;
    row.focus();
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("delete requires a confirm step — does not call onDelete on the first click", async () => {
    const onDelete = vi.fn();
    render(
      <HistorySidebar uploads={UPLOADS} selectedId={null} currentUploadId={2} onSelect={vi.fn()} onDelete={onDelete} />,
    );
    await userEvent.click(screen.getByLabelText("Delete upload loom_dev_10.csv"));
    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.getByText("Delete this upload?")).toBeInTheDocument();
  });

  it("clicking Yes after the delete icon actually deletes", async () => {
    const onDelete = vi.fn();
    render(
      <HistorySidebar uploads={UPLOADS} selectedId={null} currentUploadId={2} onSelect={vi.fn()} onDelete={onDelete} />,
    );
    await userEvent.click(screen.getByLabelText("Delete upload loom_dev_10.csv"));
    await userEvent.click(screen.getByText("Yes"));
    expect(onDelete).toHaveBeenCalledWith(1);
  });

  it("clicking No cancels the delete confirm without calling onDelete", async () => {
    const onDelete = vi.fn();
    render(
      <HistorySidebar uploads={UPLOADS} selectedId={null} currentUploadId={2} onSelect={vi.fn()} onDelete={onDelete} />,
    );
    await userEvent.click(screen.getByLabelText("Delete upload loom_dev_10.csv"));
    await userEvent.click(screen.getByText("No"));
    expect(onDelete).not.toHaveBeenCalled();
    expect(screen.queryByText("Delete this upload?")).not.toBeInTheDocument();
    expect(screen.getByText("loom_dev_10.csv")).toBeInTheDocument();
  });

  it("clicking the delete icon does not also select the row", async () => {
    const onSelect = vi.fn();
    render(
      <HistorySidebar uploads={UPLOADS} selectedId={null} currentUploadId={2} onSelect={onSelect} onDelete={vi.fn()} />,
    );
    await userEvent.click(screen.getByLabelText("Delete upload loom_dev_10.csv"));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
