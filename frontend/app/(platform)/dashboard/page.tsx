"use client";

import {
  GlobalResourceMonitor,
  InferenceThroughputGrid,
  RouterEffectivenessMatrix,
} from "@/components/dashboard";

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Performance Dashboard
        </h1>
        <p className="text-sm text-zinc-500">
          Real-time telemetry for local inference. Monitors VRAM, throughput,
          and QCS routing effectiveness.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left column: resource monitoring */}
        <GlobalResourceMonitor />

        {/* Right column: inference throughput */}
        <InferenceThroughputGrid />
      </div>

      {/* Full-width: router effectiveness */}
      <RouterEffectivenessMatrix />
    </div>
  );
}
