"use client"

import { clsx } from "clsx"
import { Loader2, Search, FileText, ListChecks, Cpu, PenLine, CheckCircle2, Code2 } from "lucide-react"

const agentColors: Record<string, string> = {
  investigate: "text-indigo-400",
  note: "text-blue-400",
  plan: "text-amber-400",
  manager: "text-purple-400",
  solve: "text-emerald-400",
  check: "text-cyan-400",
  format: "text-zinc-400",
}

const agentLabels: Record<string, string> = {
  investigate: "Investigating",
  note: "Annotating",
  plan: "Planning",
  manager: "Orchestrating",
  solve: "Solving",
  check: "Checking",
  format: "Formatting",
}

interface StreamingIndicatorProps {
  agent?: string | null
}

export function StreamingIndicator({ agent }: StreamingIndicatorProps) {
  if (!agent) return null

  const color = agentColors[agent] || "text-zinc-400"
  const label = agentLabels[agent] || agent

  return (
    <div className="flex items-center gap-2 text-xs text-zinc-500 py-1">
      <Loader2 className={clsx("h-3 w-3 animate-spin", color)} />
      <span>
        <span className={clsx("font-semibold", color)}>{label}</span>
        {" "}...
      </span>
    </div>
  )
}
