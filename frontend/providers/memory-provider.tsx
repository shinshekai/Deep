"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { recallMemory, getProfile, type MemoryRecall, type UserProfile } from "@/lib/memory";

const DEVICE_ID_KEY = "deep_device_id";

function getOrCreateDeviceId(): string {
  if (typeof window === "undefined") return "server";
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}

interface MemoryContextValue {
  deviceId: string;
  recall: (query: string, topK?: number) => Promise<MemoryRecall>;
  profile: UserProfile["profile"] | null;
  refreshProfile: () => Promise<void>;
}

const MemoryContext = createContext<MemoryContextValue | null>(null);

export function useMemory(): MemoryContextValue {
  const ctx = useContext(MemoryContext);
  if (!ctx) throw new Error("useMemory must be used within MemoryProvider");
  return ctx;
}

export function MemoryProvider({ children }: { children: ReactNode }) {
  const [deviceId] = useState<string>(getOrCreateDeviceId);
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);

  const recall = useCallback(
    (query: string, topK?: number) => recallMemory(query, deviceId, topK),
    [deviceId]
  );

  const refreshProfile = useCallback(async () => {
    try {
      const p = await getProfile(deviceId);
      setProfile(p.profile);
    } catch {
      setProfile(null);
    }
  }, [deviceId]);

  useEffect(() => {
    let mounted = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshProfile().then(() => {
      if (!mounted) return;
    });
    return () => { mounted = false; };
  }, [refreshProfile]);

  return (
    <MemoryContext.Provider value={{ deviceId, recall, profile, refreshProfile }}>
      {children}
    </MemoryContext.Provider>
  );
}
