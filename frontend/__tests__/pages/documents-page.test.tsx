import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import DocumentsPage from "@/app/(platform)/documents/page";

vi.mock("@/lib/config", () => ({
  API_BASE_URL: "http://localhost:8001/api/v1",
  secureFetch: vi.fn(),
}));

vi.mock("@/providers/websocket-provider", () => ({
  useWebSocket: vi.fn(),
}));

describe("DocumentsPage", () => {
  it("imports and renders without throwing", () => {
    expect(() => render(<DocumentsPage />)).not.toThrow();
  });
});
