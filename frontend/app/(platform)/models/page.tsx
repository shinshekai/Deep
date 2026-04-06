"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import type { ModelInfo } from "@/types/api";

const API_BASE = "http://localhost:8001";

const TIER_COLORS = {
  1: "text-emerald-400",
  2: "text-amber-400",
  3: "text-red-400",
};

const TIER_LABELS = {
  1: "T1 · Always Resident",
  2: "T2 · Semi-Resident",
  3: "T3 · On-Demand",
};

export default function ModelsPage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/models`)
      .then((r) => r.json())
      .then((data) => setModels(data))
      .catch(() => setModels([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Model Tiers</h1>
        <p className="text-sm text-zinc-500">
          Three-tier model architecture with automatic VRAM-based lifecycle
          management. Models load/unload based on VRAM pressure and query
          complexity scoring.
        </p>
      </div>

      {/* Tier overview */}
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          {
            tier: 1 as const,
            models: "Qwen3-0.6B / 1.7B",
            vram: "0.5–1.2 GB",
            kv: "K:q4_0 / V:q4_0",
            concurrent: "4",
          },
          {
            tier: 2 as const,
            models: "Qwen3-4B / 8B",
            vram: "2.5–5.5 GB",
            kv: "K:q8_0 / V:q4_0",
            concurrent: "2",
          },
          {
            tier: 3 as const,
            models: "Qwen3-14B / 30B-A3B",
            vram: "8.5–18 GB",
            kv: "K:q8_0 / V:q8_0",
            concurrent: "1",
          },
        ].map((t) => (
          <div
            key={t.tier}
            className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4"
          >
            <p className={`text-xs font-semibold ${TIER_COLORS[t.tier]}`}>
              {TIER_LABELS[t.tier]}
            </p>
            <div className="mt-3 space-y-1.5 text-xs text-zinc-500">
              <div>
                Models: <span className="text-zinc-300">{t.models}</span>
              </div>
              <div>
                VRAM: <span className="text-zinc-300">{t.vram}</span>
              </div>
              <div>
                KV Cache: <span className="text-zinc-300">{t.kv}</span>
              </div>
              <div>
                Max Concurrent:{" "}
                <span className="text-zinc-300">{t.concurrent}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Model list from backend */}
      <div>
        <h3 className="text-sm font-medium text-zinc-500 mb-3">
          Running Models
        </h3>
        {loading ? (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-6 text-center text-sm text-zinc-600">
            Loading models...
          </div>
        ) : models.length === 0 ? (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-6 text-center">
            <p className="text-sm text-zinc-600">
              No models loaded. Start LM Studio to view models here.
            </p>
            <Badge variant="zinc" className="mt-2 text-[10px]">
              GET /api/v1/models
            </Badge>
          </div>
        ) : (
          <div className="space-y-1">
            {models.map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between rounded-lg border border-zinc-800/60 bg-zinc-900/30 px-4 py-2.5"
              >
                <div className="flex items-center gap-3">
                  <span className={`text-xs font-mono font-semibold ${TIER_COLORS[m.tier]}`}>
                    T{m.tier}
                  </span>
                  <div>
                    <p className="text-sm text-zinc-300">{m.name}</p>
                    <p className="text-xs text-zinc-600">
                      {m.vram_used_mb.toFixed(0)} MB · KV: {m.kv_cache_config.cache_type_k}/{m.kv_cache_config.cache_type_v}
                    </p>
                  </div>
                </div>
                <Badge
                  variant={m.status === "loaded" ? "green" : m.status === "loading" ? "yellow" : "zinc"}
                  dot
                >
                  {m.status}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
