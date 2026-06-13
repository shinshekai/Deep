import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { secureFetch } from "@/lib/config";

// These tests verify that secureFetch attaches the X-DEEP-API-KEY header
// for backend requests (relative URLs and URLs whose origin matches the
// configured API/WS origin), and does NOT attach it for unrelated
// third-party origins. Regression for the audit HIGH finding where the
// header was only added for a hardcoded localhost:8001 host.

describe("secureFetch", () => {
  let lastInit: RequestInit | undefined;

  beforeEach(() => {
    lastInit = undefined;
    // Mock the ws-ticket endpoint + the actual request through one fetch mock.
    global.fetch = vi.fn().mockImplementation((input: unknown, init?: RequestInit) => {
      const url = typeof input === "string" ? input : (input as Request)?.url ?? String(input);
      if (url.includes("/api/auth/ws-ticket")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ token: "test-token-123" }),
        } as Response);
      }
      lastInit = init;
      return Promise.resolve({ ok: true } as Response);
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function headerValue(init: RequestInit | undefined, name: string): string | null {
    if (!init?.headers) return null;
    return new Headers(init.headers).get(name);
  }

  it("attaches the auth header for relative URLs", async () => {
    await secureFetch("/api/v1/health");
    expect(headerValue(lastInit, "X-DEEP-API-KEY")).toBe("test-token-123");
  });

  it("attaches the auth header for the localhost backend origin", async () => {
    await secureFetch("http://localhost:8001/api/v1/models");
    expect(headerValue(lastInit, "X-DEEP-API-KEY")).toBe("test-token-123");
  });

  it("does NOT attach the auth header for an unrelated third-party origin", async () => {
    await secureFetch("https://example.com/data");
    expect(headerValue(lastInit, "X-DEEP-API-KEY")).toBeNull();
  });

  it("does not overwrite an explicitly provided auth header", async () => {
    await secureFetch("/api/v1/health", {
      headers: { "X-DEEP-API-KEY": "caller-supplied" },
    });
    expect(headerValue(lastInit, "X-DEEP-API-KEY")).toBe("caller-supplied");
  });
});
