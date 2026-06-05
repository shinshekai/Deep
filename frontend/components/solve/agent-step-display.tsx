"use client";

import { useState } from "react";
import {
  Search,
  FileText,
  ListChecks,
  Cpu,
  PenLine,
  CheckCircle2,
  Code2,
  ChevronDown,
  ChevronUp,
  Clock,
} from "lucide-react";
import type { AgentStepFrame } from "@/types/api";

const agentMeta: Record<
  AgentStepFrame["agent"],
  { icon: typeof Search; label: string; color: string; bg: string; border: string }
> = {
  investigate: { 
    icon: Search, 
    label: "Investigator Agent", 
    color: "text-indigo-400", 
    bg: "bg-indigo-950/10",
    border: "border-indigo-900/30" 
  },
  note: { 
    icon: FileText, 
    label: "Note Annotator", 
    color: "text-blue-400", 
    bg: "bg-blue-950/10",
    border: "border-blue-900/30" 
  },
  plan: { 
    icon: ListChecks, 
    label: "Decomposition Planner", 
    color: "text-amber-400", 
    bg: "bg-amber-950/10",
    border: "border-amber-900/30" 
  },
  manager: { 
    icon: Cpu, 
    label: "Mission Orchestrator", 
    color: "text-purple-400", 
    bg: "bg-purple-950/10",
    border: "border-purple-900/30" 
  },
  solve: { 
    icon: PenLine, 
    label: "Synthesis Solver", 
    color: "text-emerald-400", 
    bg: "bg-emerald-950/10",
    border: "border-emerald-900/30" 
  },
  check: { 
    icon: CheckCircle2, 
    label: "Fact Checker / Validator", 
    color: "text-cyan-400", 
    bg: "bg-cyan-950/10",
    border: "border-cyan-900/30" 
  },
  format: { 
    icon: Code2, 
    label: "Citation Formatter", 
    color: "text-zinc-400", 
    bg: "bg-zinc-900/20",
    border: "border-zinc-800" 
  },
};

interface AgentStepDisplayProps {
  steps: AgentStepFrame[];
}

export function AgentStepDisplay({ steps }: AgentStepDisplayProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (steps.length === 0) return null;

  const toggleExpand = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  return (
    <div className="space-y-4">
      
      {/* Header section for live timeline */}
      <div className="flex items-center gap-2 border-b border-zinc-900 pb-2.5">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500" />
        </span>
        <span className="text-xs uppercase font-extrabold tracking-widest text-zinc-400 font-mono">Agent Solve Mission Pipeline</span>
      </div>

      <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
        {steps.map((step, i) => {
          const meta = agentMeta[step.agent] || agentMeta.manager;
          const Icon = meta.icon;
          const isLatest = i === steps.length - 1;
          const isExpanded = expandedIndex === i || isLatest;

          return (
            <div
              key={i}
              className={`rounded-xl border transition-all duration-300 ${
                isLatest
                  ? `border-l-4 border-l-indigo-500 ${meta.border} ${meta.bg}`
                  : `border-zinc-900 bg-zinc-950/40`
              }`}
            >
              
              {/* Header card toggle */}
              <div 
                onClick={() => toggleExpand(i)}
                className="flex items-center justify-between px-4 py-3 cursor-pointer select-none"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon className={`h-4.5 w-4.5 shrink-0 ${meta.color}`} />
                  <div className="min-w-0">
                    <div className="text-xs font-bold text-zinc-200">{meta.label}</div>
                    <div className="flex items-center gap-1.5 mt-0.5 text-[9px] text-zinc-500 font-mono">
                      <Clock className="h-3 w-3" />
                      <span>{new Date(step.timestamp * 1000).toLocaleTimeString()}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {isLatest && (
                    <span className="text-[9px] font-mono text-indigo-400 font-extrabold uppercase bg-indigo-950/40 border border-indigo-900/30 px-1.5 py-0.5 rounded animate-pulse">
                      Processing...
                    </span>
                  )}
                  <button type="button" aria-label="Toggle step details" aria-expanded={isExpanded} className="text-zinc-500 hover:text-white transition">
                    {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Expansive raw thought blocks */}
              {isExpanded && (
                <div className="px-4 pb-4.5 pt-1 border-t border-zinc-900/60">
                  <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-zinc-400 bg-zinc-950/80 rounded-lg p-3 border border-zinc-900/40 max-h-[260px] overflow-auto">
                    {step.content}
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
