"use client";

import {
  Search, FileText, Layers, Cpu, Sparkles,
  CheckCircle2, Code2, ChevronDown, ChevronRight,
} from "lucide-react";
import type { AgentStepFrame } from "@/types/api";

const agentMeta: Record<
  string,
  { icon: React.ComponentType<{ className?: string }>; label: string; color: string; bg: string; border: string }
> = {
  investigate: { icon: Search, label: "Investigate Agent", color: "text-indigo-400", bg: "bg-indigo-950/10", border: "border-indigo-900/30" },
  note: { icon: FileText, label: "Annotator Agent", color: "text-blue-400", bg: "bg-blue-950/10", border: "border-blue-900/30" },
  plan: { icon: Layers, label: "Planner Agent", color: "text-amber-400", bg: "bg-amber-950/10", border: "border-amber-900/30" },
  manager: { icon: Cpu, label: "Mission Controller", color: "text-purple-400", bg: "bg-purple-950/10", border: "border-purple-900/30" },
  solve: { icon: Sparkles, label: "Solve Agent", color: "text-emerald-400", bg: "bg-emerald-950/10", border: "border-emerald-900/30" },
  check: { icon: CheckCircle2, label: "Checker Agent", color: "text-cyan-400", bg: "bg-cyan-950/10", border: "border-cyan-900/30" },
  format: { icon: Code2, label: "Formatter Agent", color: "text-zinc-400", bg: "bg-zinc-900/20", border: "border-zinc-800" },
};

interface StreamingPipelineProps {
  steps: AgentStepFrame[];
  expandedStepIndex: number | null;
  onToggleStep: (index: number) => void;
}

export function StreamingPipeline({ steps, expandedStepIndex, onToggleStep }: StreamingPipelineProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 border-b border-zinc-900 pb-2">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500" />
        </span>
        <span className="text-xs uppercase font-extrabold tracking-widest text-zinc-400 font-mono">
          Agent Solve Pipeline Ingress
        </span>
      </div>

      <div className="space-y-3">
        {steps.map((step, i) => {
          const meta = agentMeta[step.agent] || agentMeta.manager;
          const Icon = meta.icon;
          const isLatest = i === steps.length - 1;
          const isExpanded = expandedStepIndex === i || isLatest;

          return (
            <div
              key={i}
              className={`rounded-xl border transition-all duration-300 ${
                isLatest
                  ? `border-l-4 border-l-indigo-500 ${meta.border} ${meta.bg}`
                  : `border-zinc-900 bg-zinc-950/40`
              }`}
            >
              <div
                onClick={() => onToggleStep(i)}
                className="flex items-center justify-between px-4 py-3 cursor-pointer select-none"
                role="button"
                aria-expanded={isExpanded}
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggleStep(i); } }}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon className={`h-4.5 w-4.5 shrink-0 ${meta.color}`} />
                  <div className="min-w-0">
                    <div className="text-xs font-bold text-zinc-200">{meta.label}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {isLatest && (
                    <span className="text-[9px] font-mono text-indigo-400 font-extrabold uppercase bg-indigo-950/40 border border-indigo-900/30 px-1.5 py-0.5 rounded animate-pulse">
                      Processing...
                    </span>
                  )}
                  {isExpanded ? <ChevronDown className="h-4 w-4 text-zinc-500" /> : <ChevronRight className="h-4 w-4 text-zinc-500" />}
                </div>
              </div>

              {isExpanded && (
                <div className="px-4 pb-4 pt-1 border-t border-zinc-900/60 select-text">
                  <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-zinc-400 bg-zinc-950/80 rounded-lg p-3 border border-zinc-900/40 max-h-60 overflow-auto">
                    {step.content || "Accumulating delta thoughts..."}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
