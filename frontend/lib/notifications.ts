// Pub-sub notification bus — decouples toast notifications from React tree.
// Non-React code (WebSocket manager, event handlers) can emit notifications
// which are bridged to Sonner by the app's <Toaster> provider.
//
// Usage from anywhere (React or non-React):
//   import { notify } from "@/lib/notifications";
//   notify.info("Connected to server");
//   notify.warning("VRAM at 90%");
//   notify.error("Connection lost");

type NotificationType = "info" | "success" | "warning" | "error" | "loading";

interface NotificationPayload {
  type: NotificationType;
  message: string;
  description?: string;
  duration?: number;
  id?: string;
}

type Subscriber = (payload: NotificationPayload) => void;

class NotificationBus {
  private _subscribers: Set<Subscriber> = new Set();

  subscribe(cb: Subscriber): () => void {
    this._subscribers.add(cb);
    return () => this._subscribers.delete(cb);
  }

  private _emit(payload: NotificationPayload) {
    for (const cb of this._subscribers) {
      try {
        cb(payload);
      } catch {
        // Swallow subscriber errors so one bad handler doesn't break others
      }
    }
  }

  info(message: string, description?: string) {
    this._emit({ type: "info", message, description });
  }

  success(message: string, description?: string) {
    this._emit({ type: "success", message, description });
  }

  warning(message: string, description?: string) {
    this._emit({ type: "warning", message, description, duration: 5000 });
  }

  error(message: string, description?: string) {
    this._emit({ type: "error", message, description, duration: 8000 });
  }

  loading(message: string, description?: string) {
    this._emit({ type: "loading", message, description });
  }
}

export const notify = new NotificationBus();
