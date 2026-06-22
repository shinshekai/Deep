"use client";

import { useState, useEffect } from "react";
import {
  GlobalResourceMonitor,
  InferenceThroughputGrid,
  RouterEffectivenessMatrix,
  LiveAgentThinking,
} from "@/components/dashboard";
import { MemoryGraph } from "@/components/memory/memory-graph";
import { useWebSocket } from "@/providers/websocket-provider";
import { useMemory } from "@/providers/memory-provider";
import { getMemoryStats } from "@/lib/memory";
import type { MemoryStats } from "@/lib/memory";
import { Activity } from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { metricsStatus } = useWebSocket();
  const connected = metricsStatus === "open";
  const { deviceId } = useMemory();
  const [stats, setStats] = useState<MemoryStats | null>(null);

  useEffect(() => {
    if (!deviceId) return;
    getMemoryStats(deviceId).then(setStats).catch(() => setStats(null));
  }, [deviceId]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Performance Dashboard
        </h1>
        <p className="text-sm text-zinc-500">
          Real-time telemetry from the ws/metrics stream (2s interval). Monitors
          VRAM pressure, model tier throughput, and routing effectiveness.
        </p>
      </div>

      {!connected ? (
        <div className="rounded-xl border border-dashed border-zinc-900 p-12 text-center bg-zinc-950/10">
          <Activity className="mx-auto mb-3 h-10 w-10 text-zinc-850 animate-pulse" />
          <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider font-mono">
            Awaiting Metrics Stream
          </h3>
          <p className="text-xs text-zinc-600 mt-1 max-w-xs mx-auto leading-relaxed">
            Start a Solve session or run inference to populate this dashboard
            with live VRAM, throughput, and routing telemetry. Data arrives via
            the <code className="text-zinc-500">ws/metrics</code> WebSocket.
          </p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <Link
              href="/chat"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition"
            >
              Start Chat
            </Link>
            <Link
              href="/solve"
              className="rounded-lg border border-zinc-800 px-4 py-2 text-xs font-semibold text-zinc-400 hover:border-zinc-700 hover:text-zinc-300 transition"
            >
              Solve Problem
            </Link>
          </div>
        </div>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Left column: resource monitoring */}
            <GlobalResourceMonitor />

            {/* Right column: inference throughput */}
            <InferenceThroughputGrid />
          </div>

          {/* Full-width: router effectiveness */}
          <RouterEffectivenessMatrix />

          <LiveAgentThinking />

          <MemoryGraph
            stats={stats ? {
              total_episodes: stats.episodes,
              total_facts: stats.facts,
              total_dead_ends: stats.total_dead_ends,
              total_strategies: stats.total_strategies,
            } : undefined}
          />
        </>
      )}
    </div>
  );
}
