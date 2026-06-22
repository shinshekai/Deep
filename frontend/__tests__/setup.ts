import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

vi.mock("@/providers/theme-provider", () => ({
  useTheme: () => ({ theme: "dark", setTheme: vi.fn(), themes: [] }),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/providers/websocket-provider", () => ({
  useWebSocket: () => ({
    solveStatus: "open",
    metricsStatus: "open", 
    vram: null,
    pressure: null,
    latestMetrics: null,
    subscribe: vi.fn(() => vi.fn()),
    send: vi.fn(),
    ws: { connectSolve: vi.fn(), connectMetrics: vi.fn(), disconnect: vi.fn() },
  }),
  WebSocketProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/providers/memory-provider", () => ({
  useMemory: () => ({ episodes: [], facts: [], stats: {} }),
  MemoryProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/providers/store-provider", () => ({
  useAppStore: vi.fn(() => ({})),
  AppStoreProvider: ({ children }: { children: React.ReactNode }) => children,
}));
