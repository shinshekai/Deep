import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { GlobalResourceMonitor } from "@/components/dashboard/global-resource-monitor";

// Mock the websocket provider
vi.mock("@/providers/websocket-provider", () => ({
  useWebSocket: vi.fn(),
}));

import { useWebSocket } from "@/providers/websocket-provider";

describe("GlobalResourceMonitor component", () => {
  it("renders awaiting data state when no vram/pressure data is provided", () => {
    vi.mocked(useWebSocket).mockReturnValue({
      vram: null,
      pressure: null,
    } as any);

    render(<GlobalResourceMonitor />);
    expect(screen.getByText("Awaiting data…")).toBeInTheDocument();
    expect(screen.getByText(/Connect to the FastAPI backend/)).toBeInTheDocument();
  });

  it("renders correctly with mock vram data", () => {
    vi.mocked(useWebSocket).mockReturnValue({
      vram: {
        vram_total_mb: 24000,
        vram_used_mb: 8000,
        vram_used_pct: 33.3,
        pressure_level: "green",
        active_models: [{ name: "Qwen3-1.7B" }],
        turboquant_tier: "auto",
      },
      pressure: "green",
    } as any);

    render(<GlobalResourceMonitor />);
    
    // Total VRAM
    expect(screen.getByText("24,000")).toBeInTheDocument();
    // Used VRAM
    expect(screen.getByText("8,000")).toBeInTheDocument();
    // Free VRAM
    expect(screen.getByText("16,000")).toBeInTheDocument();
    
    // Active models
    expect(screen.getByText(/Qwen3-1.7B/)).toBeInTheDocument();
    
    // Pressure indicator
    expect(screen.getByText(/GREEN — 33.3% — < 70% — Normal/i)).toBeInTheDocument();
  });
});
