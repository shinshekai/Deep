"use client"

import { useState } from "react"
import { clsx } from "clsx"
import {
  Search, FileText, ListChecks, Cpu, PenLine,
  CheckCircle2, Code2, ChevronDown, ChevronUp,
  Clock, Loader2
} from "lucide-react"
import type { AgentStepFrame } from "@/types/api"

const agentMeta: Record<
  AgentStepFrame["agent"],
  { icon: typeof Search; label: string; color: string; bg: string; border: string }
> = {
  investigate: {
    icon: Search,
    label: "Investigator",
    color: "text-indigo-400",
    bg: "bg-indigo-950/10",
    border: "border-indigo-900/30",
  },
  note: {
    icon: FileText,
    label: "Annotator",
    color: "text-blue-400",
    bg: "bg-blue-950/10",
    border: "border-blue-900/30",
  },
  plan: {
    icon: ListChecks,
    label: "Planner",
    color: "text-amber-400",
    bg: "bg-amber-950/10",
    border: "border-amber-900/30",
  },
  manager: {
    icon: Cpu,
    label: "Controller",
    color: "text-purple-400",
    bg: "bg-purple-950/10",
    border: "border-purple-900/30",
  },
  solve: {
    icon: PenLine,
    label: "Solver",
    color: "text-emerald-400",
    bg: "bg-emerald-950/10",
    border: "border-emerald-900/30",
  },
  check: {
    icon: CheckCircle2,
    label: "Checker",
    color: "text-cyan-400",
    bg: "bg-cyan-950/10",
    border: "border-cyan-900/30",
  },
  format: {
    icon: Code2,
    label: "Formatter",
    color: "text-zinc-400",
    bg: "bg-zinc-900/20",
    border: "border-zinc-800",
  },
}

interface AgentStepCardProps {
  step: AgentStepFrame
  isLatest?: boolean
  defaultExpanded?: boolean
}

export function AgentStepCard({ step, isLatest = false, defaultExpanded }: AgentStepCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded ?? isLatest)
  const meta = agentMeta[step.agent] || agentMeta.manager
  const Icon = meta.icon

  return (
    <div
      className={clsx(
        "rounded-xl border transition-all duration-300",
        isLatest
          ? `border-l-4 border-l-indigo-500 ${meta.border} ${meta.bg}`
          : "border-zinc-900 bg-zinc-950/40"
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3 text-left select-none"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {isLatest ? (
            <Loader2 className={clsx("h-4 w-4 shrink-0 animate-spin", meta.color)} />
          ) : (
            <Icon className={clsx("h-4 w-4 shrink-0", meta.color)} />
          )}
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
          <span className="text-zinc-500 hover:text-white transition">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-zinc-900/60">
          <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-zinc-400 bg-zinc-950/80 rounded-lg p-3 border border-zinc-900/40 max-h-[260px] overflow-auto">
            {step.content}
          </pre>
        </div>
      )}
    </div>
  )
}

interface AgentStepTimelineProps {
  steps: AgentStepFrame[]
}

export function AgentStepTimeline({ steps }: AgentStepTimelineProps) {
  if (steps.length === 0) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 border-b border-zinc-900 pb-2.5">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500" />
        </span>
        <span className="text-xs uppercase font-extrabold tracking-widest text-zinc-400 font-mono">
          Agent Pipeline
        </span>
      </div>

      <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
        {steps.map((step, i) => (
          <AgentStepCard
            key={i}
            step={step}
            isLatest={i === steps.length - 1}
          />
        ))}
      </div>
    </div>
  )
}
