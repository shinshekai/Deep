import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SolveInput } from "@/components/solve/solve-input";

describe("SolveInput component", () => {
  it("renders correctly with default state", () => {
    render(<SolveInput onSend={vi.fn()} isStreaming={false} />);
    expect(screen.getByPlaceholderText("Ask a question about your documents...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /solve/i })).toBeDisabled();
  });

  it("enables submit button when text is entered", async () => {
    render(<SolveInput onSend={vi.fn()} isStreaming={false} />);
    const input = screen.getByPlaceholderText("Ask a question about your documents...");
    await userEvent.type(input, "What is the meaning of life?");
    expect(screen.getByRole("button", { name: /solve/i })).not.toBeDisabled();
  });

  it("calls onSend with correct parameters when submitted", async () => {
    const onSendMock = vi.fn();
    render(<SolveInput onSend={onSendMock} isStreaming={false} />);
    
    const input = screen.getByPlaceholderText("Ask a question about your documents...");
    await userEvent.type(input, "Test query");
    
    const button = screen.getByRole("button", { name: /solve/i });
    fireEvent.click(button);
    
    expect(onSendMock).toHaveBeenCalledWith({
      query: "Test query",
      kb_name: "",
      mode: "auto",
      retrieval_pipeline: "tree",
    });
  });

  it("disables inputs when streaming", () => {
    render(<SolveInput onSend={vi.fn()} isStreaming={true} />);
    expect(screen.getByPlaceholderText("Ask a question about your documents...")).toBeDisabled();
    expect(screen.getByRole("button", { name: /solving\.\.\./i })).toBeDisabled();
  });
});
