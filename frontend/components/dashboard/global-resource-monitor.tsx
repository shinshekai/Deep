"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useWebSocket } from "@/providers/websocket-provider";
import type { CacheTelemetry } from "@/types/api";

function conditionVariant(state: string): "green" | "yellow" | "red" {
  return (state as "green" | "yellow" | "red") ?? "green";
}

export function GlobalResourceMonitor() {
  const { cacheTelemetry } = useWebSocket();

  // In production this would be maintained in context from WebSocket + polling
  // For scaffold we render what we have
  if (!cacheTelemetry) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Global Resource Monitor</CardTitle>
          <Badge variant="zinc" dot>Awaiting data…</Badge>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-500">
            Connect to the FastAPI backend to view VRAM and cache metrics.
          </p>
        </CardContent>
      </Card>
    );
  }

  const t = cacheTelemetry as CacheTelemetry;
  const vramFree = t.vram_total_mb - t.vram_allocated_mb;
  const pctUsed = Math.round(
    (t.vram_allocated_mb / t.vram_total_mb) * 100
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Global Resource Monitor</CardTitle>
        <Badge variant={conditionVariant(t.condition_state)} dot>
          {t.condition_state.toUpperCase()} — {pctUsed}% VRAM
        </Badge>
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs text-zinc-500">Total VRAM</div>
            <div className="font-mono text-lg">
              {t.vram_total_mb.toLocaleString()} MB
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Allocated</div>
            <div className="font-mono text-lg">
              {t.vram_allocated_mb.toLocaleString()} MB
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Free</div>
            <div className="font-mono text-lg">
              {vramFree.toLocaleString()} MB
            </div>
          </div>
        </div>

        <div className="mt-4 text-xs text-zinc-500">
          <span className="font-medium">Active models:</span>{" "}
          {t.active_models.length > 0
            ? t.active_models.join(", ")
            : "None loaded"}
        </div>

        <div className="mt-1 text-xs text-zinc-500">
          <span className="font-medium">KV compression:</span>{" "}
          <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono">
            {t.kv_compression_type}
          </span>
        </div>

        {/* Sparkline placeholder — wired up in Step 9 */}
        <div className="mt-4 h-24 rounded-lg bg-zinc-900/50 flex items-center justify-center text-xs text-zinc-600">
          Memory pressure sparkline (60s trailing)
        </div>
      </CardContent>
    </Card>
  );
}
