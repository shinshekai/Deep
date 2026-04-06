"use client";

import { useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { fetchMetricsHistory } from "@/lib/websocket";
import type { MetricsFrame, RoutingStats } from "@/types/api";

const POLL_INTERVAL = 5000; // Section 5: 5-second polling cadence

export function RouterEffectivenessMatrix() {
  const [stats, setStats] = useState<RoutingStats | null>(null);

  useEffect(() => {
    const poll = async () => {
      const data = await fetchMetricsHistory();
      if (data) {
        setStats(data as unknown as RoutingStats);
      }
    };
    poll();
    const id = setInterval(poll, POLL_INTERVAL);
    return () => clearInterval(id);
  }, []);

  if (!stats) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Router Effectiveness Matrix</CardTitle>
          <Badge variant="zinc">No data</Badge>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-500">
            Polling
            <span className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs">
              GET /api/telemetry/routing-stats
            </span>{" "}
            every {POLL_INTERVAL / 1000}s. Connect the backend to view
            historical routing metrics.
          </p>
        </CardContent>
      </Card>
    );
  }

  const metrics = [
    { label: "Cache Hit Rate", value: stats.cache_hit_rate, suffix: "%" },
    { label: "JIT Load Freq.", value: stats.jit_load_frequency },
    { label: "Evictions", value: stats.eviction_count },
    { label: "Model Hit Rate", value: stats.model_hit_rate, suffix: "%" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Router Effectiveness Matrix</CardTitle>
        <Badge variant="zinc">Last updated: {new Date().toLocaleTimeString()}</Badge>
      </CardHeader>

      <CardContent>
        {/* Key metrics */}
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {metrics.map((m) => (
            <div
              key={m.label}
              className="flex flex-col gap-1 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3"
            >
              <div className="text-xs text-zinc-500">{m.label}</div>
              <div className="font-mono text-lg">
                {typeof m.value === "number" ? m.value.toLocaleString() : "—"}
                {m.suffix ?? ""}
              </div>
            </div>
          ))}
        </div>

        {/* Model tier breakdown */}
        {stats.queries_by_tier && stats.queries_by_tier.length > 0 && (
          <div className="mt-2">
            <div className="mb-2 text-xs font-medium text-zinc-500">
              Queries by Tier
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart
                data={stats.queries_by_tier}
                margin={{ top: 5, right: 10, bottom: 5, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="tier"
                  tickFormatter={(v) => `Tier ${v}`}
                  stroke="#52525b"
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                />
                <YAxis
                  stroke="#52525b"
                  tick={{ fill: "#a1a1aa", fontSize: 11 }}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    borderColor: "#27272a",
                    borderRadius: 8,
                    color: "#fafafa",
                  }}
                  formatter={(value) => [`${value}`, "Queries"]}
                />
                <Bar
                  dataKey="count"
                  fill="#6366f1"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Fallback info */}
        {!stats.queries_by_tier?.length && (
          <div className="mt-2 text-xs text-zinc-600">
            No tier breakdown data available yet.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
