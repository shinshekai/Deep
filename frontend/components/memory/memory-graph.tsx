"use client";

import { useMemo } from "react";
import { Brain, FileText, AlertTriangle, Layers } from "lucide-react";

interface GraphNode {
  id: string;
  label: string;
  type: "episode" | "fact" | "dead_end" | "strategy";
  x: number;
  y: number;
  connections: string[];
}

interface MemoryGraphProps {
  stats?: {
    total_episodes: number;
    total_facts: number;
    total_dead_ends: number;
    total_strategies: number;
  };
}

function generateNodes(stats: MemoryGraphProps["stats"]): GraphNode[] {
  const nodes: GraphNode[] = [];
  const centerX = 400;
  const centerY = 250;

  const types = [
    { key: "episode", count: Math.min(stats.total_episodes, 15), label: "Episode", color: "indigo" },
    { key: "fact", count: Math.min(stats.total_facts, 15), label: "Fact", color: "emerald" },
    { key: "dead_end", count: Math.min(stats.total_dead_ends, 10), label: "Dead End", color: "rose" },
    { key: "strategy", count: Math.min(stats.total_strategies, 5), label: "Strategy", color: "amber" },
  ];

  let idx = 0;
  for (const { key, count, label } of types) {
    for (let i = 0; i < count; i++) {
      const angle = (idx / (count * types.length)) * Math.PI * 2;
      const radius = 80 + Math.random() * 150;
      nodes.push({
        id: `${key}-${i}`,
        label: `${label} ${i + 1}`,
        type: key as GraphNode["type"],
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
        connections: [],
      });
      idx++;
    }
  }

  // Connect nearby nodes of different types
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      if (nodes[i].type !== nodes[j].type) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        if (Math.sqrt(dx * dx + dy * dy) < 120) {
          nodes[i].connections.push(nodes[j].id);
        }
      }
    }
  }

  return nodes;
}

const TYPE_CONFIG = {
  episode: { color: "indigo", icon: Brain, size: 8 },
  fact: { color: "emerald", icon: FileText, size: 6 },
  dead_end: { color: "rose", icon: AlertTriangle, size: 7 },
  strategy: { color: "amber", icon: Layers, size: 5 },
};

export function MemoryGraph({ stats }: MemoryGraphProps) {
  const resolved = stats ?? { total_episodes: 0, total_facts: 0, total_dead_ends: 0, total_strategies: 0 };
  const nodes = useMemo(() => generateNodes(resolved), [resolved]);
  const total = nodes.length;
  if (total === 0) return null;

  const connections = new Set<string>();
  nodes.forEach((n) => n.connections.forEach((c) => connections.add(`${n.id}-${c}`)));

  return (
    <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-6 space-y-4">
      <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono border-b border-zinc-900 pb-2">
        <Brain className="h-3.5 w-3.5 text-indigo-400" />
        <span>Memory Graph</span>
        <span className="text-zinc-600 font-normal ml-auto">{total} nodes</span>
      </div>

      <svg viewBox="0 0 800 500" className="w-full h-80">
        {Array.from(connections).map((key) => {
          const [from, to] = key.split("-");
          const fromNode = nodes.find((n) => n.id === from);
          const toNode = nodes.find((n) => n.id === to);
          if (!fromNode || !toNode) return null;
          return (
            <line
              key={key}
              x1={fromNode.x}
              y1={fromNode.y}
              x2={toNode.x}
              y2={toNode.y}
              stroke="oklch(0.5 0 0 / 0.15)"
              strokeWidth={1}
            />
          );
        })}

        {nodes.map((node) => {
          const config = TYPE_CONFIG[node.type];
          return (
            <g key={node.id}>
              <circle
                cx={node.x}
                cy={node.y}
                r={config.size}
                fill={`oklch(var(--${config.color}-500) / 0.3)`}
                stroke={`oklch(var(--${config.color}-500) / 0.6)`}
                strokeWidth={1.5}
                className="transition-all hover:r-[10] cursor-pointer"
              />
              <text
                x={node.x}
                y={node.y + config.size + 12}
                textAnchor="middle"
                className="fill-zinc-500"
                style={{ fontSize: "9px", fontFamily: "monospace" }}
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>

      <div className="flex justify-center gap-4 text-[9px] font-mono text-zinc-500">
        {Object.entries(TYPE_CONFIG).map(([key, config]) => (
          <div key={key} className="flex items-center gap-1.5">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: `oklch(var(--${config.color}-500) / 0.6)` }}
            />
            {key.replace("_", " ")} ({nodes.filter((n) => n.type === key).length})
          </div>
        ))}
      </div>
    </div>
  );
}
