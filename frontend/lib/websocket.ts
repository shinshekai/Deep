import { API_BASE_URL, WS_BASE_URL, secureFetch, getWsAuthToken } from "./config";

const API_BASE = API_BASE_URL.replace(/\/api\/v1\/?$/, "");

type MessageCallback = (data: Record<string, unknown>) => void;
type Status = "connecting" | "open" | "closed" | "error";

export class WebSocketManager {
  private static instance: WebSocketManager;
  private solveConnection: WebSocket | null = null;
  private metricsConnection: WebSocket | null = null;
  private solveStatus: Status = "closed";
  private metricsStatus: Status = "closed";
  private solveSubscribers = new Map<string, Set<MessageCallback>>();
  private metricsSubscribers = new Map<string, Set<MessageCallback>>();
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

  // ──────────────────────────────────────────
  // Smart Solver WebSocket
  // ──────────────────────────────────────────

  async connectSolve(): Promise<void> {
    const url = await buildWsUrl("/api/v1/solve");
    return this._connect("solve", url, (ws) => { this.solveConnection = ws; },
      () => this.solveStatus, (s) => { this.solveStatus = s; },
      this.solveSubscribers, this.metricsSubscribers);
  }

  // ──────────────────────────────────────────
  // Metrics WebSocket
  // ──────────────────────────────────────────

  async connectMetrics(): Promise<void> {
    const url = await buildWsUrl("/ws/metrics");
    return this._connect("metrics", url, (ws) => { this.metricsConnection = ws; },
      () => this.metricsStatus, (s) => { this.metricsStatus = s; },
      this.metricsSubscribers, this.solveSubscribers);
  }

  // ──────────────────────────────────────────
  // Shared connection logic
  // ──────────────────────────────────────────

  private _connect(
    name: string,
    url: string,
    setWs: (ws: WebSocket) => void,
    getStatus: () => Status,
    setStatus: (s: Status) => void,
    subscribers: Map<string, Set<MessageCallback>>,
    _otherSubscribers: Map<string, Set<MessageCallback>> // eslint-disable-line @typescript-eslint/no-unused-vars
  ): Promise<void> {
    return new Promise((resolve) => {
      if (this._getWs(name)?.readyState === WebSocket.OPEN) {
        setStatus("open");
        resolve();
        return;
      }

      setStatus("connecting");
      this._notify(subscribers, "_connection", { connection: name, status: "open" });

      try {
        const ws = new WebSocket(url);
        setWs(ws);

        ws.onopen = async () => {
          setStatus("open");
          this.reconnectAttempts = 0;
          const token = await getWsAuthToken();
          if (token) {
            ws.send(JSON.stringify({ type: "auth", token }));
          }
          this._notify(subscribers, "_connection", { connection: name, status: "open" });
          resolve();
        };

        ws.onmessage = (event: MessageEvent) => {
          try {
            const message = JSON.parse(event.data);
            const data: Record<string, unknown> =
              "data" in message ? (message.data as Record<string, unknown>) : message;
            this._notify(subscribers, message.type ?? "message", data);
          } catch {
            this._notify(subscribers, "_raw", { connection: name, text: String(event.data) });
          }
        };

        ws.onclose = () => {
          setStatus("closed");
          this._notify(subscribers, "_connection", { connection: name, status: "close" });
          this._scheduleReconnect(name);
        };

        ws.onerror = () => {
          setStatus("error");
          this._notify(subscribers, "_connection", { connection: name, status: "error" });
        };
      } catch {
        setStatus("error");
        this._scheduleReconnect(name);
        resolve();
      }
    });
  }

  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this.solveConnection?.close();
    this.metricsConnection?.close();
    this.solveConnection = null;
    this.metricsConnection = null;
    this.solveStatus = "closed";
    this.metricsStatus = "closed";
    this.resetReconnectAttempts();
  }

  // ──────────────────────────────────────────
  // Send via solve connection (primary API)
  // ──────────────────────────────────────────

  send(data: Record<string, unknown>): void {
    if (this.solveConnection?.readyState === WebSocket.OPEN) {
      this.solveConnection.send(JSON.stringify(data));
    }
  }

  subscribe(
    eventType: string,
    callback: MessageCallback
  ): () => void {
    for (const map of [this.solveSubscribers, this.metricsSubscribers]) {
      if (!map.has(eventType)) {
        map.set(eventType, new Set());
      }
      map.get(eventType)!.add(callback);
    }
    return () => {
      this.solveSubscribers.get(eventType)?.delete(callback);
      this.metricsSubscribers.get(eventType)?.delete(callback);
    };
  }

  getStatus(): Status {
    return this.solveStatus;
  }

  getMetricsStatus(): Status {
    return this.metricsStatus;
  }

  private _getWs(name: string): WebSocket | null {
    return name === "solve" ? this.solveConnection : this.metricsConnection;
  }

  private _notify(
    subscribers: Map<string, Set<MessageCallback>>,
    eventType: string,
    data: Record<string, unknown>
  ): void {
    subscribers.get(eventType)?.forEach((cb) => cb(data));
  }

  private _scheduleReconnect(
    name: string
  ): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    this.reconnectTimeout = setTimeout(() => {
      if (name === "solve") {
        this.connectSolve();
      } else {
        this.connectMetrics();
      }
    }, delay);
  }

  private resetReconnectAttempts(): void {
    this.reconnectAttempts = 0;
  }
}

async function buildWsUrl(path: string): Promise<string> {
  return `${WS_BASE_URL}${path}`;
}

// ─────────────────────────────────────────────
// REST API helpers (UDIP API :8001)
// ─────────────────────────────────────────────

/** GET /api/v1/metrics/history — timeseries for dashboard charts */
export async function fetchMetricsHistory(): Promise<Record<string, unknown> | null> {
  try {
    const res = await secureFetch(`${API_BASE}/api/v1/metrics/history`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** GET /api/v1/vram/status — current GPU VRAM pressure level */
export async function fetchVramStatus(): Promise<Record<string, unknown> | null> {
  try {
    const res = await secureFetch(`${API_BASE}/api/v1/vram/status`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** GET /api/v1/models — list all models with tier assignments */
export async function fetchModels(): Promise<Record<string, unknown> | null> {
  try {
    const res = await secureFetch(`${API_BASE}/api/v1/models`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

/** GET /api/v1/health — system health check */
export async function fetchHealth(): Promise<Record<string, unknown> | null> {
  try {
    const res = await secureFetch(`${API_BASE}/api/v1/health`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
