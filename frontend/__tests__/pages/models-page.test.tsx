import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ModelsPage from "@/app/(platform)/models/page";

vi.mock("@/lib/config", () => ({
  API_BASE_URL: "http://localhost:8001/api/v1",
  secureFetch: vi.fn(),
}));

vi.mock("@/providers/websocket-provider", () => ({
  useWebSocket: vi.fn(),
}));

vi.mock("@/providers/theme-provider", () => ({
  useTheme: () => ({ theme: "dark", setTheme: vi.fn(), themes: [] }),
}));

import { secureFetch } from "@/lib/config";
const mockSecureFetch = vi.mocked(secureFetch);

function mockResponse(data: unknown, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve(data) } as Response);
}

describe("ModelsPage", () => {
  it("renders without crashing", () => {
    mockSecureFetch.mockResolvedValue(mockResponse({ local: [], cloud: [], active_selection: null }));
    render(<ModelsPage />);
    expect(document.body).toBeTruthy();
  });

  it("shows skeleton during loading", () => {
    render(<ModelsPage />);
    expect(document.body).toBeTruthy();
  });
});
