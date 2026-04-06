const WS_URL = "ws://127.0.0.1:8000/ws";
const API_BASE = "http://127.0.0.1:8000";

type MessageCallback = (data: Record<string, unknown>) => void;
type Status = "connecting" | "open" | "closed" | "error";

export class WebSocketManager {
  private static instance: WebSocketManager;
  private ws: WebSocket | null = null;
  private status: Status = "closed";
  private subscribers = new Map<string, Set<MessageCallback>>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  private constructor() {}

  static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager();
    }
    return WebSocketManager.instance;
  }

  connect(): Promise<void> {
    return new Promise((resolve) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.status = "open";
        resolve();
        return;
      }

      this.status = "connecting";
      this.notify("connection", { status: "open" as const });

      try {
        this.ws = new WebSocket(WS_URL);

        this.ws.onopen = () => {
          this.status = "open";
          this.reconnectAttempts = 0;
          this.notify("connection", { status: "open" });
          resolve();
        };

        this.ws.onmessage = (event: MessageEvent) => {
          try {
            const message = JSON.parse(event.data);
            const data: Record<string, unknown> =
              "data" in message ? (message.data as Record<string, unknown>) : message;
            this.notify(message.type, data);
          } catch {
            // Non-JSON message, ignore
          }
        };

        this.ws.onclose = () => {
          this.status = "closed";
          this.notify("connection", { status: "close" });
          this.scheduleReconnect();
        };

        this.ws.onerror = () => {
          this.status = "error";
          this.notify("connection", { status: "error" });
        };
      } catch {
        this.status = "error";
        this.scheduleReconnect();
        resolve();
      }
    });
  }

  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.status = "closed";
    this.resetReconnectAttempts();
  }

  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  subscribe(
    eventType: string,
    callback: MessageCallback
  ): () => void {
    if (!this.subscribers.has(eventType)) {
      this.subscribers.set(eventType, new Set());
    }
    this.subscribers.get(eventType)!.add(callback);

    return () => {
      this.subscribers.get(eventType)?.delete(callback);
    };
  }

  getStatus(): Status {
    return this.status;
  }

  private notify(eventType: string, data: Record<string, unknown>): void {
    this.subscribers.get(eventType)?.forEach((cb) => cb(data));
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private resetReconnectAttempts(): void {
    this.reconnectAttempts = 0;
  }
}

// ─────────────────────────────────────────────
// REST API helpers (for routing stats polling)
// ─────────────────────────────────────────────

export async function fetchCacheTelemetry(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_BASE}/api/telemetry/routing-stats`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function fetchHealth(): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
