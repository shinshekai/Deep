"use client";

import { Gauge, RefreshCw, Layers } from "lucide-react";
import { Badge } from "@/components/ui/badge";

type ActiveSelection = { model_id: string; provider_id: string } | null;

interface ModelsHeaderProps {
  telemetry: {
    total_mb: number;
    used_mb: number;
    utilization_pct: number;
    pressure_level: string;
  };
  loading: boolean;
  activeSelections: Record<string, ActiveSelection>;
  onRefresh: () => void;
}

export function ModelsHeader({ telemetry, loading, activeSelections, onRefresh }: ModelsHeaderProps) {
  const pressureColor =
    telemetry.pressure_level === "red"
      ? "bg-red-500"
      : telemetry.pressure_level === "orange"
        ? "bg-orange-500"
        : telemetry.pressure_level === "yellow"
          ? "bg-yellow-500"
          : "bg-emerald-500";

  const pressureTextColor =
    telemetry.pressure_level === "red"
      ? "text-red-400"
      : telemetry.pressure_level === "orange"
        ? "text-orange-400"
        : telemetry.pressure_level === "yellow"
          ? "text-yellow-400"
          : "text-emerald-400";

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-md px-6 py-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white uppercase font-sans">Models Console</h1>
            <Badge className="bg-indigo-600/10 text-indigo-400 border-indigo-900/30 text-[10px] uppercase tracking-wider font-mono">v2.0</Badge>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5">
            Dual-loop multi-agent orchestration console for the DEEP local document pipeline.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4 bg-zinc-900/50 border border-zinc-850 rounded-lg px-4 py-2.5">
          <div className="flex items-center gap-2">
            <Gauge className="h-4 w-4 text-zinc-400" />
            <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">GPU Memory:</span>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative h-2 w-32 rounded-full bg-zinc-800 overflow-hidden">
              <div
                className={`absolute h-full rounded-full transition-all duration-500 ${pressureColor}`}
                style={{ width: `${telemetry.utilization_pct}%` }}
              />
            </div>
            <span className="text-xs font-semibold font-mono text-zinc-200">
              {Math.round(telemetry.used_mb / 1024)} / {Math.round(telemetry.total_mb / 1024)} GB
            </span>
            <span className="text-[10px] font-mono text-zinc-400">({Math.round(telemetry.utilization_pct)}%)</span>
          </div>

          <div className="h-4 w-[1px] bg-zinc-800" />

          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${pressureTextColor}`} />
              <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${pressureColor}`} />
            </span>
            <span className="text-xs uppercase font-bold text-zinc-300 tracking-wide font-mono">
              {telemetry.pressure_level}
            </span>
          </div>

          <button
            type="button"
            disabled={loading}
            onClick={onRefresh}
            className="flex h-7 w-7 items-center justify-center rounded border border-zinc-800 hover:border-zinc-700 bg-zinc-950 text-zinc-400 hover:text-white transition focus:outline-none"
            title="Refresh models index"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3 items-center text-xs bg-indigo-950/10 border-t border-zinc-900 pt-3">
        <span className="flex items-center gap-1 text-[10px] uppercase font-mono text-zinc-500 tracking-wider font-bold">
          <Layers className="h-3 w-3 text-indigo-400" /> Active Routes:
        </span>
        <span className="flex items-center gap-1 text-zinc-300">
          <span className="text-[10px] font-bold text-indigo-400 font-mono">T1</span>
          <span className="font-semibold text-zinc-200">
            {activeSelections.T1 ? activeSelections.T1.model_id : "Safe Fallback Cascade"}
          </span>
        </span>
        <span className="text-zinc-600">/</span>
        <span className="flex items-center gap-1 text-zinc-300">
          <span className="text-[10px] font-bold text-indigo-400 font-mono">T2</span>
          <span className="font-semibold text-zinc-200">
            {activeSelections.T2 ? activeSelections.T2.model_id : "Safe Fallback Cascade"}
          </span>
        </span>
        <span className="text-zinc-600">/</span>
        <span className="flex items-center gap-1 text-zinc-300">
          <span className="text-[10px] font-bold text-indigo-400 font-mono">T3</span>
          <span className="font-semibold text-zinc-200">
            {activeSelections.T3 ? activeSelections.T3.model_id : "Safe Fallback Cascade"}
          </span>
        </span>
      </div>
    </header>
  );
}
