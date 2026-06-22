"use client";

import { useEffect } from "react";

const SYNC_CHANNEL = "deep-cross-tab";

export function useCrossTabSync(
  onMessage: (data: Record<string, unknown>) => void,
  channel = SYNC_CHANNEL
) {
  useEffect(() => {
    try {
      const bc = new BroadcastChannel(channel);
      bc.onmessage = (event) => onMessage(event.data as Record<string, unknown>);
      return () => bc.close();
    } catch {
      const onStorage = (e: StorageEvent) => {
        if (e.key === channel && e.newValue) {
          try {
            onMessage(JSON.parse(e.newValue));
          } catch {}
        }
      };
      window.addEventListener("storage", onStorage);
      return () => window.removeEventListener("storage", onStorage);
    }
  }, [onMessage, channel]);
}

export function sendCrossTabMessage(data: Record<string, unknown>, channel = SYNC_CHANNEL) {
  try {
    const bc = new BroadcastChannel(channel);
    bc.postMessage(data);
    bc.close();
  } catch {
    localStorage.setItem(channel, JSON.stringify({ ...data, _ts: Date.now() }));
    localStorage.removeItem(channel);
  }
}
