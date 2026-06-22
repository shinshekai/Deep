import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import NotebooksPage from "@/app/(platform)/notebooks/page";

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

describe("NotebooksPage", () => {
  it("renders without crashing", async () => {
    mockSecureFetch.mockResolvedValue(mockResponse([]));
    render(<NotebooksPage />);
    expect(document.body).toBeTruthy();
  });
});
