"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { WebSocketManager, fetchCacheTelemetry } from "@/lib/websocket";
import type { CacheTelemetry, RoutingStats } from "@/types/api";

// ─────────────────────────────────────────────
// Context
// ─────────────────────────────────────────────

interface WebSocketContextValue {
  ws: WebSocketManager;
  status: "connecting" | "open" | "closed" | "error";
  conditionState: "green" | "yellow" | "red" | null;
  cacheTelemetry: CacheTelemetry | null;
  routingStats: RoutingStats | null;
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
  const [status, setStatus] = useState<WebSocketContextValue["status"]>(
    "connecting"
  );
  const [conditionState, setConditionState] =
    useState<WebSocketContextValue["conditionState"]>(null);
  const [cacheTelemetry, setCacheTelemetry] = useState<CacheTelemetry | null>(
    null
  );
  const [routingStats, setRoutingStats] = useState<RoutingStats | null>(null);

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

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    ws.connect();

    return () => {
      ws.disconnect();
    };
  }, [ws]);

  // Subscribe to connection status
  useEffect(() => {
    return ws.subscribe("connection", (data) => {
      setStatus(data.status as WebSocketContextValue["status"]);
    });
  }, [ws]);

  // Subscribe to cache telemetry events
  useEffect(() => {
    return ws.subscribe("cache", (data) => {
      setConditionState(data.condition_state as "green" | "yellow" | "red" | null);
      setCacheTelemetry(data as unknown as CacheTelemetry);
    });
  }, [ws]);

  // Poll routing stats via REST (every 5s) — Section 5 of inference strategy
  useEffect(() => {
    const poll = async () => {
      const data = await fetchCacheTelemetry();
      if (data) {
        setConditionState(data.condition_state as "green" | "yellow" | "red" | null);
        setCacheTelemetry(data as unknown as CacheTelemetry);
        setRoutingStats(data as unknown as RoutingStats);
      }
    };

    poll();
    const interval = setInterval(poll, 5000);
    return () => clearInterval(interval);
  }, [ws]);

  return (
    <WebSocketContext.Provider
      value={{ ws, status, conditionState, cacheTelemetry, routingStats, subscribe, send }}
    >
      {children}
    </WebSocketContext.Provider>
  );
}
