"use client";

import {
  Search,
  FileText,
  ListChecks,
  Cpu,
  PenLine,
  CheckCircle2,
  Code2,
} from "lucide-react";
import type { AgentStepFrame } from "@/types/api";

const agentMeta: Record<
  AgentStepFrame["agent"],
  { icon: typeof Search; label: string; color: string }
> = {
  investigate: { icon: Search, label: "Investigate", color: "text-indigo-400" },
  note: { icon: FileText, label: "Note", color: "text-blue-400" },
  plan: { icon: ListChecks, label: "Plan", color: "text-amber-400" },
  manager: { icon: Cpu, label: "Manager", color: "text-purple-400" },
  solve: { icon: PenLine, label: "Solve", color: "text-emerald-400" },
  check: { icon: CheckCircle2, label: "Check", color: "text-cyan-400" },
  format: { icon: Code2, label: "Format", color: "text-zinc-400" },
};

interface AgentStepDisplayProps {
  steps: AgentStepFrame[];
}

export function AgentStepDisplay({ steps }: AgentStepDisplayProps) {
  if (steps.length === 0) return null;

  return (
    <div className="space-y-3">
      {steps.map((step, i) => {
        const meta = agentMeta[step.agent];
        const Icon = meta.icon;
        const isLast = i === steps.length - 1;

        return (
          <div
            key={i}
            className={`flex gap-3 rounded-lg border border-zinc-800/60 bg-zinc-900/40 px-4 py-3 ${isLast ? "border-l-2 border-l-indigo-500" : ""}`}
          >
            <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${meta.color}`} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold ${meta.color}`}>
                  {meta.label}
                </span>
                <span className="text-[10px] text-zinc-600">
                  {new Date(step.timestamp * 1000).toLocaleTimeString()}
                </span>
              </div>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-xs leading-relaxed text-zinc-300">
                {step.content}
              </pre>
            </div>
          </div>
        );
      })}

      {/* Thinking indicator for latest step */}
      {steps.length > 0 && (
        <div className="ml-7 flex items-center gap-1.5 text-xs text-zinc-500">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" />
          Processing...
        </div>
      )}
    </div>
  );
}
