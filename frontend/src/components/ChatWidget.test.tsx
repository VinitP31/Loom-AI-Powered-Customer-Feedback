import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ChatWidget from "./ChatWidget";
import * as chatClient from "../api/chatClient";

describe("ChatWidget", () => {
  it("orb closed by default, opens the chat panel on click", async () => {
    render(<ChatWidget dashboardSnapshotId={5} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Chat with tickets" }));
    expect(screen.getByRole("dialog", { name: "Chat with tickets" })).toBeInTheDocument();
  });

  it("closing hides the panel again", async () => {
    render(<ChatWidget dashboardSnapshotId={5} />);
    await userEvent.click(screen.getByRole("button", { name: "Chat with tickets" }));
    await userEvent.click(screen.getByRole("button", { name: "Close chat" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("defaults to 'This dashboard' scope and sends it with the question", async () => {
    const spy = vi.spyOn(chatClient, "sendChatMessage").mockResolvedValue({ answer: "Ticket 1 is a login issue.", sources: [] });
    render(<ChatWidget dashboardSnapshotId={7} />);
    await userEvent.click(screen.getByRole("button", { name: "Chat with tickets" }));

    await userEvent.type(screen.getByPlaceholderText("Ask about these tickets…"), "who is having login trouble?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(spy).toHaveBeenCalledWith("who is having login trouble?", "dashboard", 7));
    expect(await screen.findByText("Ticket 1 is a login issue.")).toBeInTheDocument();
  });

  it("switching to 'All history' sends scope=all with a null snapshot id", async () => {
    const spy = vi.spyOn(chatClient, "sendChatMessage").mockResolvedValue({ answer: "Two weeks report billing issues.", sources: [] });
    render(<ChatWidget dashboardSnapshotId={7} />);
    await userEvent.click(screen.getByRole("button", { name: "Chat with tickets" }));

    await userEvent.click(screen.getByText("All history"));
    await userEvent.type(screen.getByPlaceholderText("Ask about these tickets…"), "any billing issues?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(spy).toHaveBeenCalledWith("any billing issues?", "all", null));
  });

  it("renders cited ticket sources under the assistant's answer", async () => {
    vi.spyOn(chatClient, "sendChatMessage").mockResolvedValue({
      answer: "Ticket 1 reports a login failure.",
      sources: [{ ticket_id: "1", snapshot_id: 7, source_filename: "week1.csv", similarity: 0.49 }],
    });
    render(<ChatWidget dashboardSnapshotId={7} />);
    await userEvent.click(screen.getByRole("button", { name: "Chat with tickets" }));
    await userEvent.type(screen.getByPlaceholderText("Ask about these tickets…"), "login trouble?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    const chip = await screen.findByText("1");
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveAttribute("title", "week1.csv · similarity 0.49");
  });

  it("shows an error message when the chat call fails, without crashing", async () => {
    vi.spyOn(chatClient, "sendChatMessage").mockRejectedValue(new Error("Could not reach the chat backend."));
    render(<ChatWidget dashboardSnapshotId={7} />);
    await userEvent.click(screen.getByRole("button", { name: "Chat with tickets" }));
    await userEvent.type(screen.getByPlaceholderText("Ask about these tickets…"), "anything?");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Could not reach the chat backend.")).toBeInTheDocument();
  });

  it("'This dashboard' scope is disabled when there's no current snapshot id", async () => {
    render(<ChatWidget dashboardSnapshotId={null} />);
    await userEvent.click(screen.getByRole("button", { name: "Chat with tickets" }));
    expect(screen.getByText("This dashboard")).toBeDisabled();
  });
});
