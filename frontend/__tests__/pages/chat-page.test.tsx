import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatPage from "@/app/(platform)/chat/page";

vi.mock("@/lib/config", () => ({
  API_BASE_URL: "http://localhost:8001/api/v1",
  secureFetch: vi.fn(),
}));

vi.mock("@/providers/websocket-provider", () => ({
  useWebSocket: vi.fn(),
}));

vi.mock("@/lib/use-upload-polling", () => ({
  useUploadPolling: vi.fn(),
}));

vi.mock("@/lib/knowledge", () => ({
  uploadDocument: vi.fn(),
  pollUploadTask: vi.fn(),
  fetchKnowledgeBases: vi.fn(),
}));

import { secureFetch } from "@/lib/config";
import { useWebSocket } from "@/providers/websocket-provider";
import { fetchKnowledgeBases } from "@/lib/knowledge";

const mockSecureFetch = vi.mocked(secureFetch);
const mockUseWebSocket = vi.mocked(useWebSocket);
const mockFetchKnowledgeBases = vi.mocked(fetchKnowledgeBases);

function mockFetchResponse(data: unknown, ok = true) {
  return Promise.resolve({
    ok,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("ChatPage", () => {
  const originalScrollIntoView = HTMLElement.prototype.scrollIntoView;

  beforeEach(() => {
    vi.clearAllMocks();
    HTMLElement.prototype.scrollIntoView = vi.fn();
    mockUseWebSocket.mockReturnValue({
      solveStatus: "closed",
      send: vi.fn(),
      subscribe: vi.fn(() => vi.fn()),
    } as unknown as ReturnType<typeof useWebSocket>);
    mockFetchKnowledgeBases.mockResolvedValue([]);
    mockSecureFetch.mockImplementation((input: RequestInfo | URL) => {
      const urlString = typeof input === "string" ? input : (input instanceof URL ? input.toString() : input.url);
      if (urlString.includes("/notebooks")) return mockFetchResponse([]);
      if (urlString.includes("/models")) return mockFetchResponse([]);
      return mockFetchResponse([]);
    });
  });

  afterEach(() => {
    HTMLElement.prototype.scrollIntoView = originalScrollIntoView;
  });

  const renderChatPage = async () => {
    const utils = render(<ChatPage />);
    await waitFor(() => {
      expect(mockFetchKnowledgeBases).toHaveBeenCalled();
      expect(mockSecureFetch).toHaveBeenCalledWith(expect.stringContaining("/notebooks"));
      expect(mockSecureFetch).toHaveBeenCalledWith(expect.stringContaining("/models"));
    });
    return utils;
  };

  it("renders welcome screen with suggestion cards", async () => {
    await renderChatPage();
    expect(screen.getByText(/Scribble\. Upload\. Synthesize/)).toBeInTheDocument();
    expect(screen.getByText("Summarize Workspace")).toBeInTheDocument();
    expect(screen.getByText("Synthesize Gaps")).toBeInTheDocument();
    expect(screen.getByText("Compare Architectures")).toBeInTheDocument();
  });

  it("renders chat input textarea", async () => {
    await renderChatPage();
    expect(screen.getByLabelText("Ask a question")).toBeInTheDocument();
  });

  it("renders sidebar toggle buttons", async () => {
    await renderChatPage();
    expect(screen.getByLabelText("Toggle sources sidebar")).toBeInTheDocument();
    expect(screen.getByLabelText("Toggle notebook panel")).toBeInTheDocument();
  });

  it("renders KB selector in left sidebar", async () => {
    await renderChatPage();
    await waitFor(() => {
      expect(screen.getByLabelText("Select active knowledge base")).toBeInTheDocument();
    });
  });

  it("renders notebook selector in right sidebar", async () => {
    await renderChatPage();
    await waitFor(() => {
      expect(screen.getByLabelText("Select target notebook")).toBeInTheDocument();
    });
  });

  it("renders retrieval pipeline selector", async () => {
    await renderChatPage();
    expect(screen.getByLabelText("Select retrieval pipeline")).toBeInTheDocument();
  });

  it("renders solve mode selector", async () => {
    await renderChatPage();
    expect(screen.getByLabelText("Select solve mode")).toBeInTheDocument();
  });

  it("send button is disabled when input is empty", async () => {
    await renderChatPage();
    const sendBtn = screen.getByLabelText("Send message");
    expect(sendBtn).toBeDisabled();
  });

  it("send button enables when text is entered", async () => {
    await renderChatPage();
    const textarea = screen.getByLabelText("Ask a question");
    await userEvent.type(textarea, "What is attention?");
    const sendBtn = screen.getByLabelText("Send message");
    expect(sendBtn).not.toBeDisabled();
  });

  it("shows WS OFFLINE indicator when disconnected", async () => {
    mockUseWebSocket.mockReturnValue({
      solveStatus: "closed",
      send: vi.fn(),
      subscribe: vi.fn(() => vi.fn()),
    } as unknown as ReturnType<typeof useWebSocket>);
    await renderChatPage();
    expect(screen.getByText("WS OFFLINE")).toBeInTheDocument();
  });

  it("hides WS OFFLINE indicator when connected", async () => {
    mockUseWebSocket.mockReturnValue({
      solveStatus: "open",
      send: vi.fn(),
      subscribe: vi.fn(() => vi.fn()),
    } as unknown as ReturnType<typeof useWebSocket>);
    await renderChatPage();
    expect(screen.queryByText("WS OFFLINE")).not.toBeInTheDocument();
  });

  it("loads knowledge bases on mount", async () => {
    mockFetchKnowledgeBases.mockResolvedValue([
      { name: "kb-1" },
      { name: "kb-2" },
    ]);
    await renderChatPage();
    await waitFor(() => {
      expect(mockFetchKnowledgeBases).toHaveBeenCalled();
    });
  });

  it("renders notebook creation button", async () => {
    await renderChatPage();
    expect(screen.getByLabelText("Open construct notebook")).toBeInTheDocument();
  });

  it("left sidebar shows Sources Scope header", async () => {
    await renderChatPage();
    expect(screen.getByText("Sources Scope")).toBeInTheDocument();
  });

  it("right sidebar shows Notebook Annotations header", async () => {
    await renderChatPage();
    expect(screen.getByText("Notebook Annotations")).toBeInTheDocument();
  });
});
