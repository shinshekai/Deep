import { create } from "zustand";

interface ActiveSelection {
  model_id: string;
  provider_id?: string;
  provider_type?: string;
}

export interface AppStore {
  modelSelection: Record<string, ActiveSelection | null>;
  apiCache: Record<string, { data: unknown; ts: number }>;
  setModelSelection: (tier: string, sel: ActiveSelection | null) => void;
  setCachedApiResponse: (key: string, data: unknown) => void;
  getCachedApiResponse: (key: string, maxAgeMs?: number) => unknown | null;
  clearCache: () => void;
}

export const useAppStore = create<AppStore>((set, get) => ({
  modelSelection: {},
  apiCache: {},

  setModelSelection: (tier, sel) =>
    set((state) => ({
      modelSelection: { ...state.modelSelection, [tier]: sel },
    })),

  setCachedApiResponse: (key, data) =>
    set((state) => ({
      apiCache: { ...state.apiCache, [key]: { data, ts: Date.now() } },
    })),

  getCachedApiResponse: (key, maxAgeMs = 30000) => {
    const entry = get().apiCache[key];
    if (!entry) return null;
    if (Date.now() - entry.ts > maxAgeMs) return null;
    return entry.data;
  },

  clearCache: () => set({ apiCache: {} }),
}));
