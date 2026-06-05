import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GuidedLearningPage from "@/app/(platform)/guide/page";

vi.mock("@/lib/config", () => ({
  API_BASE_URL: "http://localhost:8001/api/v1",
  secureFetch: vi.fn(),
}));

import { secureFetch } from "@/lib/config";

const mockSecureFetch = vi.mocked(secureFetch);

function mockFetchResponse(data: unknown, ok = true) {
  return Promise.resolve({
    ok,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("GuidedLearningPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSecureFetch.mockImplementation(() =>
      mockFetchResponse([])
    );
  });

  it("renders the setup screen with title and topic input", async () => {
    render(<GuidedLearningPage />);
    expect(screen.getByText("Guided AI Tutor")).toBeInTheDocument();
    expect(screen.getByLabelText("Learning topic")).toBeInTheDocument();
    expect(screen.getByLabelText("Start guided learning session")).toBeInTheDocument();
  });

  it("renders suggestion buttons", () => {
    render(<GuidedLearningPage />);
    expect(screen.getByText(/Transformers attention/)).toBeInTheDocument();
    expect(screen.getByText(/Quantum Cryptography/)).toBeInTheDocument();
    expect(screen.getByText(/KV Cache Quantization/)).toBeInTheDocument();
  });

  it("populates KB selector from API", async () => {
    mockSecureFetch.mockImplementation(() =>
      mockFetchResponse([{ name: "research-papers" }, { name: "textbooks" }])
    );
    render(<GuidedLearningPage />);
    await waitFor(() => {
      expect(screen.getByText("research-papers")).toBeInTheDocument();
      expect(screen.getByText("textbooks")).toBeInTheDocument();
    });
  });

  it("disables start button when topic is empty", () => {
    render(<GuidedLearningPage />);
    const btn = screen.getByLabelText("Start guided learning session");
    expect(btn).toBeDisabled();
  });

  it("enables start button when topic is entered", async () => {
    render(<GuidedLearningPage />);
    const input = screen.getByLabelText("Learning topic");
    await userEvent.type(input, "Attention mechanism");
    const btn = screen.getByLabelText("Start guided learning session");
    expect(btn).not.toBeDisabled();
  });

  it("clicking suggestion sets the topic", async () => {
    render(<GuidedLearningPage />);
    const suggestion = screen.getByText(/Transformers attention/);
    await userEvent.click(suggestion);
    const input = screen.getByLabelText("Learning topic") as HTMLInputElement;
    expect(input.value).toContain("Transformers");
  });

  it("displays error banner when KB fetch fails", async () => {
    mockSecureFetch.mockImplementation(() =>
      Promise.reject(new Error("network error"))
    );
    render(<GuidedLearningPage />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText(/Failed to load knowledge bases/)).toBeInTheDocument();
    });
  });

  it("error banner can be dismissed", async () => {
    mockSecureFetch.mockImplementation(() =>
      Promise.reject(new Error("network error"))
    );
    render(<GuidedLearningPage />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    const dismissBtn = screen.getByLabelText("Dismiss error");
    await userEvent.click(dismissBtn);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders KB scope label", () => {
    render(<GuidedLearningPage />);
    expect(screen.getByText("Knowledge Base Scope")).toBeInTheDocument();
  });
});
