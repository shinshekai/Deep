"use client";

import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
  Cell,
} from "recharts";
import { useWebSocket } from "@/providers/websocket-provider";
import type { InferenceTelemetryEvent, PipelineStage } from "@/types/api";

const stageColors: Record<PipelineStage, string> = {
  PageIndex_Retrieval: "#6366f1",
  DeepTutor_Reasoning: "#f59e0b",
  Final_Synthesis: "#10b981",
};

const stageBadgeVariant: Record<PipelineStage, "blue" | "yellow" | "green"> =
  {
    PageIndex_Retrieval: "blue",
    DeepTutor_Reasoning: "yellow",
    Final_Synthesis: "green",
  };

export function InferenceThroughputGrid() {
  const { latestMetrics } = useWebSocket();
  const [tick, setTick] = useState<number>(0);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (latestMetrics) setTick(Date.now());
  }, [latestMetrics]);

  const events: InferenceTelemetryEvent[] = (
    latestMetrics?.active_models ?? []
  ).map((modelId) => ({
    model_id: modelId,
    timestamp: tick,
    pipeline_stage: "Final_Synthesis",
    ttft_ms: latestMetrics?.latency_ms ?? 0,
    tps_rate: latestMetrics?.throughput_tps ?? 0,
    total_tokens_processed: 0,
    kv_compression_ratio: 0,
  }));

  if (events.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Inference Throughput Grid</CardTitle>
          <Badge variant="zinc">No active streams</Badge>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-zinc-500">
            Active inference streams will appear here once the backend begins
            processing queries.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Inference Throughput Grid</CardTitle>
        <Badge variant="blue">{events.length} stream(s)</Badge>
      </CardHeader>

      <CardContent>
        {/* Metric cards */}
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {events.slice(-4).map((ev, i) => (
            <div
              key={i}
              className="flex flex-col gap-1 rounded-lg border border-zinc-800 bg-zinc-900/60 p-3"
            >
              <div className="text-xs text-zinc-500 truncate">
                {ev.model_id}
              </div>
              <div className="font-mono text-lg">{ev.tps_rate.toFixed(1)}</div>
              <div className="text-xs text-zinc-500">TPS</div>
              <Badge variant={stageBadgeVariant[ev.pipeline_stage]}>
                {ev.pipeline_stage}
              </Badge>
              <div className="text-xs text-zinc-500">
                TTFT: {ev.ttft_ms.toFixed(0)}ms
              </div>
            </div>
          ))}
        </div>

        {/* Chart */}
        <ResponsiveContainer width="100%" height={180}>
          <BarChart
            data={events.map((ev) => ({
              model: ev.model_id,
              tps: ev.tps_rate,
              ttft: ev.ttft_ms,
              stage: ev.pipeline_stage,
            }))}
          >
            <XAxis
              dataKey="model"
              stroke="#52525b"
              tick={{ fill: "#a1a1aa", fontSize: 10 }}
            />
            <YAxis
              stroke="#52525b"
              tick={{ fill: "#a1a1aa", fontSize: 10 }}
              label={{
                value: "TPS",
                angle: -90,
                position: "insideLeft",
                fill: "#71717a",
                fontSize: 10,
              }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#18181b",
                borderColor: "#27272a",
                borderRadius: 8,
                color: "#fafafa",
              }}
            />
            <Bar dataKey="tps" radius={[4, 4, 0, 0]}>
              {events.map((ev) => (
                <Cell
                  key={ev.timestamp}
                  fill={stageColors[ev.pipeline_stage] ?? "#6366f1"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
