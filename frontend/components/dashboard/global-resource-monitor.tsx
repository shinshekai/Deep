"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useWebSocket } from "@/providers/websocket-provider";
import type { VramPressureLevel } from "@/types/api";

const pressureColors: Record<VramPressureLevel, string> = {
  green: "text-emerald-500",
  yellow: "text-yellow-500",
  orange: "text-orange-500",
  red: "text-red-500",
};

const pressureDot: Record<VramPressureLevel, string> = {
  green: "bg-emerald-500",
  yellow: "bg-yellow-500",
  orange: "bg-orange-500",
  red: "bg-red-500",
};

const pressureBorder: Record<VramPressureLevel, string> = {
  green: "border-emerald-500/20",
  yellow: "border-yellow-500/20",
  orange: "border-orange-500/20",
  red: "border-red-500/20",
};

const pressureBg: Record<VramPressureLevel, string> = {
  green: "bg-emerald-500/10",
  yellow: "bg-yellow-500/10",
  orange: "bg-orange-500/10",
  red: "bg-red-500/10",
};

const pressureLabel: Record<VramPressureLevel, string> = {
  green: "< 70% — Normal",
  yellow: "70–85% — Degraded",
  orange: "85–93% — Emergency",
  red: "> 93% — Critical",
};

export function GlobalResourceMonitor() {
  const { vram, pressure } = useWebSocket();

  if (!vram && !pressure) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Global Resource Monitor</CardTitle>
          <Badge variant="zinc" dot>Awaiting data…</Badge>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-500">
            Connect to the FastAPI backend (localhost:8001) to view VRAM and
            cache metrics.
          </p>
        </CardContent>
      </Card>
    );
  }

  const vramUsed = vram?.vram_used_mb ?? 0;
  const vramTotal = vram?.vram_total_mb ?? 0;
  const vramFree = vramTotal - vramUsed;
  const pct = vram?.vram_used_pct ?? 0;
  const level = vram?.pressure_level ?? (pressure ?? "green");

  const activeModelNames = vram?.active_models?.map((m) => {
    // m could be ModelInfo or string in fallback
    return typeof m === "string" ? m : m.name;
  }) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Global Resource Monitor</CardTitle>
        <Badge
          className={`${pressureBg[level]} ${pressureColors[level]} ${pressureBorder[level]}`}
          dot
        >
          <span className={`h-1.5 w-1.5 rounded-full ${pressureDot[level]}`} />
          {level.toUpperCase()} — {pct}% — {pressureLabel[level]}
        </Badge>
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs text-zinc-500">Total VRAM</div>
            <div className="font-mono text-lg">
              {vramTotal ? vramTotal.toLocaleString() : "—"} MB
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Used</div>
            <div className="font-mono text-lg">
              {vramUsed ? vramUsed.toLocaleString() : "—"} MB
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Free</div>
            <div className="font-mono text-lg">
              {vramFree ? vramFree.toLocaleString() : "—"} MB
            </div>
          </div>
        </div>

        <div className="mt-4 text-xs text-zinc-500">
          <span className="font-medium">Active models:</span>{" "}
          {activeModelNames.length > 0
            ? activeModelNames.join(", ")
            : "None loaded"}
        </div>

        {vram?.turboquant_tier && (
          <div className="mt-1 text-xs text-zinc-500">
            <span className="font-medium">TurboQuant:</span>{" "}
            <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono">
              {vram.turboquant_tier}
            </span>
          </div>
        )}

        {/* Sparkline placeholder — wired up when metrics stream is live */}
        <div className="mt-4 h-24 rounded-lg bg-zinc-900/50 flex items-center justify-center text-xs text-zinc-600">
          Memory pressure sparkline (2s polling via ws/metrics)
        </div>
      </CardContent>
    </Card>
  );
}