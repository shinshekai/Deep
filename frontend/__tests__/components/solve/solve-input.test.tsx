import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SolveInput } from "@/components/solve/solve-input";

vi.mock("@/lib/config", () => ({
  API_BASE_URL: "http://localhost:8001/api/v1",
  secureFetch: vi.fn(),
}));

import { secureFetch } from "@/lib/config";
const mockSecureFetch = vi.mocked(secureFetch);

describe("SolveInput component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSecureFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);
  });

  const renderSolveInput = async (props: { onSend: any; isStreaming: boolean }) => {
    const utils = render(<SolveInput {...props} />);
    await waitFor(() => {
      expect(mockSecureFetch).toHaveBeenCalled();
    });
    return utils;
  };

  it("renders correctly with default state", async () => {
    await renderSolveInput({ onSend: vi.fn(), isStreaming: false });
    expect(screen.getByPlaceholderText("Ask DEEP anything about your document workspace...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /solve/i })).toHaveAttribute("aria-disabled", "true");
  });

  it("enables submit button when text is entered", async () => {
    await renderSolveInput({ onSend: vi.fn(), isStreaming: false });
    const input = screen.getByPlaceholderText("Ask DEEP anything about your document workspace...");
    await userEvent.type(input, "What is the meaning of life?");
    expect(screen.getByRole("button", { name: /solve/i })).toHaveAttribute("aria-disabled", "false");
  });

  it("calls onSend with correct parameters when submitted", async () => {
    const onSendMock = vi.fn();
    await renderSolveInput({ onSend: onSendMock, isStreaming: false });
    
    const input = screen.getByPlaceholderText("Ask DEEP anything about your document workspace...");
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

  it("disables inputs when streaming", async () => {
    await renderSolveInput({ onSend: vi.fn(), isStreaming: true });
    expect(screen.getByPlaceholderText("Ask DEEP anything about your document workspace...")).toBeDisabled();
    expect(screen.getByRole("button", { name: /solve/i })).toHaveAttribute("aria-disabled", "true");
  });
});
