"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useWebSocket } from "@/providers/websocket-provider";
import type { VramPressureLevel } from "@/types/api";
import { AreaChart, Area, ResponsiveContainer } from "recharts";

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
  const [history, setHistory] = useState<{ timestamp: string; pct: number }[]>([]);

  useEffect(() => {
    if (!vram) return;
    const pct = vram.vram_used_pct;
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHistory((prev) => {
      const next = [...prev, { timestamp: time, pct }];
      if (next.length > 20) return next.slice(-20);
      return next;
    });
  }, [vram]);

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
  const pct = Math.round(vram?.vram_used_pct ?? 0);
  const level = vram?.pressure_level ?? (pressure ?? "green");

  const activeModelNames = vram?.active_models?.map((m) => {
    return typeof m === "string" ? m : m.name;
  }) ?? [];

  const sparklineColor =
    level === "red"
      ? "#ef4444"
      : level === "orange"
        ? "#f97316"
        : level === "yellow"
          ? "#eab308"
          : "#6366f1";

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
            <div className="font-mono text-lg text-zinc-200">
              {vramTotal ? (vramTotal / 1024).toFixed(1) : "—"} GB
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Used</div>
            <div className="font-mono text-lg text-zinc-200">
              {vramUsed ? (vramUsed / 1024).toFixed(1) : "—"} GB
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Free</div>
            <div className="font-mono text-lg text-zinc-200">
              {vramFree ? (vramFree / 1024).toFixed(1) : "—"} GB
            </div>
          </div>
        </div>

        <div className="mt-4 text-xs text-zinc-400">
          <span className="font-semibold text-zinc-500">Active models:</span>{" "}
          {activeModelNames.length > 0
            ? activeModelNames.join(", ")
            : "None loaded"}
        </div>

        {vram?.turboquant_tier && (
          <div className="mt-1.5 text-xs text-zinc-400">
            <span className="font-semibold text-zinc-500">TurboQuant:</span>{" "}
            <span className="rounded bg-zinc-800/60 border border-zinc-700/35 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300">
              {vram.turboquant_tier}
            </span>
          </div>
        )}

        {/* Live memory sparkline graph */}
        <div className="mt-5 h-24 rounded-xl bg-zinc-950/60 border border-zinc-900 overflow-hidden relative p-1">
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                <defs>
                  <linearGradient id="vramGlow" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={sparklineColor} stopOpacity={0.25}/>
                    <stop offset="95%" stopColor={sparklineColor} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="pct"
                  stroke={sparklineColor}
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#vramGlow)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-[10px] font-mono text-zinc-600">
              Awaiting telemetry packets...
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}