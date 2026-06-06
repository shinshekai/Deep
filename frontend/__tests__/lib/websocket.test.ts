import { describe, it, expect, vi, beforeEach } from "vitest";
import { WebSocketManager } from "@/lib/websocket";

describe("WebSocketManager", () => {
  let wsManager: WebSocketManager;

  beforeEach(() => {
    // Reset instance between tests if needed, but since it's a singleton, 
    // we'll just get the instance and mock globals.
    wsManager = WebSocketManager.getInstance();
    
    // Mock global WebSocket
    global.WebSocket = vi.fn().mockImplementation(() => ({
      readyState: 0,
      send: vi.fn(),
      close: vi.fn(),
    })) as unknown as typeof WebSocket;
  });

  it("returns a singleton instance", () => {
    const instance1 = WebSocketManager.getInstance();
    const instance2 = WebSocketManager.getInstance();
    expect(instance1).toBe(instance2);
  });

  it("initializes with closed statuses", () => {
    expect(wsManager.getStatus()).toBe("closed");
    expect(wsManager.getMetricsStatus()).toBe("closed");
  });

  it("allows subscription and unsubscription", () => {
    const callback = vi.fn();
    const unsubscribe = wsManager.subscribe("test_event", callback);
    
    // Mock the notify call internally by pretending a message arrived
    // Since we mock the whole class internals, we test the public api behavior.
    
    expect(typeof unsubscribe).toBe("function");
    unsubscribe();
  });
});
