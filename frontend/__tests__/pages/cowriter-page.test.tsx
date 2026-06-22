import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import CowriterPage from "@/app/(platform)/cowriter/page";

vi.mock("@/lib/config", () => ({
  API_BASE_URL: "http://localhost:8001/api/v1",
  secureFetch: vi.fn(),
}));
vi.mock("@/providers/websocket-provider", () => ({ useWebSocket: vi.fn() }));
vi.mock("@/providers/theme-provider", () => ({
  useTheme: () => ({ theme: "dark", setTheme: vi.fn(), themes: [] }),
}));

import { secureFetch } from "@/lib/config";
const mockSecureFetch = vi.mocked(secureFetch);

function mockResponse(data: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(data) } as Response);
}

describe("CowriterPage", () => {
  it("renders co-writer interface", async () => {
    mockSecureFetch.mockResolvedValue(mockResponse([]));
    render(<CowriterPage />);
    const el = await screen.findByPlaceholderText(/Type, outline, or paste raw materials/i, {}, { timeout: 3000 });
    expect(el).toBeInTheDocument();
  });
});
