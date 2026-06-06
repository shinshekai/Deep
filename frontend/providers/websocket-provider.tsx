"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { WebSocketManager } from "@/lib/websocket";
import type { CacheTelemetry, MetricsFrame, VramPressureLevel } from "@/types/api";

// ─────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────

interface WebSocketContextValue {
  ws: WebSocketManager;
  solveStatus: "connecting" | "open" | "closed" | "error";
  metricsStatus: "connecting" | "open" | "closed" | "error";
  vram: CacheTelemetry | null;
  pressure: VramPressureLevel | null;
  latestMetrics: MetricsFrame | null;
  subscribe: (
    eventType: string,
    callback: (data: Record<string, unknown>) => void
  ) => () => void;
  send: (data: Record<string, unknown>) => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export function useWebSocket(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error("useWebSocket must be used within WebSocketProvider");
  }
  return ctx;
}

// ─────────────────────────────────────────────
// Provider
// ─────────────────────────────────────────────

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [ws] = useState(() => WebSocketManager.getInstance());
  const [solveStatus, setSolveStatus] =
    useState<WebSocketContextValue["solveStatus"]>("connecting");
  const [metricsStatus, setMetricsStatus] =
    useState<WebSocketContextValue["metricsStatus"]>("connecting");
  const [vram, setVram] = useState<CacheTelemetry | null>(null);
  const [pressure, setPressure] =
    useState<VramPressureLevel | null>(null);
  const [latestMetrics, setLatestMetrics] = useState<MetricsFrame | null>(null);

  const subscribe: WebSocketContextValue["subscribe"] = useCallback(
    (eventType, callback) => {
      return ws.subscribe(eventType, callback);
    },
    [ws]
  );

  const send: WebSocketContextValue["send"] = useCallback(
    (data) => ws.send(data),
    [ws]
  );

  // Connect both WebSocket endpoints on mount
  useEffect(() => {
    ws.connectSolve();
    ws.connectMetrics();

    return () => {
      ws.disconnect();
    };
  }, [ws]);

  // Subscribe to solve connection status
  useEffect(() => {
    return ws.subscribe("_connection", (data) => {
      if (data.connection === "solve") {
        setSolveStatus(data.status as WebSocketContextValue["solveStatus"]);
      }
    });
  }, [ws]);

  // Subscribe to metrics connection status
  useEffect(() => {
    return ws.subscribe("_connection", (data) => {
      if (data.connection === "metrics") {
        setMetricsStatus(data.status as WebSocketContextValue["metricsStatus"]);
      }
    });
  }, [ws]);

  // Subscribe to metrics stream frames
  useEffect(() => {
    return ws.subscribe("metrics_frame", (data) => {
      const frame = data as unknown as MetricsFrame;
      setLatestMetrics(frame);
      if (frame.pressure_level) {
        setPressure(frame.pressure_level as VramPressureLevel);
      }
      setVram({
        vram_total_mb: frame.vram_total_mb,
        vram_used_mb: frame.vram_used_mb,
        vram_used_pct: frame.vram_total_mb > 0 ? (frame.vram_used_mb / frame.vram_total_mb) * 100 : 0,
        pressure_level: frame.pressure_level,
        active_models: (frame.active_models || []).map((name) => ({
          id: name,
          name: name,
          tier: 3,
          status: "loaded",
          vram_used_mb: 0,
          max_concurrent: 1,
        })),
        turboquant_tier: "auto",
      });
    });
  }, [ws]);

  // Subscribe to solve agent steps
  useEffect(() => {
    return ws.subscribe("agent_step", (_data: Record<string, unknown>) => {
      // Will be consumed by chat page
    });
  }, [ws]);

  // VRAM telemetry comes exclusively from the metrics_frame WebSocket event (set above).
  // No REST polling needed — eliminates duplicate traffic and pressure flickering.

  return (
    <WebSocketContext.Provider
      value={{
        ws,
        solveStatus,
        metricsStatus,
        vram,
        pressure,
        latestMetrics,
        subscribe,
        send,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
}