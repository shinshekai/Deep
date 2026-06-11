"use client";

import { Sparkles } from "lucide-react";

const DEFAULT_PROMPTS = [
  "Identify any conflicting claims in these papers.",
  "Draft a step-by-step summary of the experimental results.",
  "Explain the theoretical formula derivation details.",
];

interface SuggestedPromptsProps {
  onSelectPrompt: (prompt: string) => void;
}

export function SuggestedPrompts({ onSelectPrompt }: SuggestedPromptsProps) {
  return (
    <div className="rounded-xl border border-zinc-900/60 bg-zinc-950 p-5 space-y-4 select-none">
      <div className="flex items-center gap-2 text-indigo-400">
        <Sparkles className="h-5 w-5 animate-pulse" />
        <h2 className="text-sm font-bold text-zinc-200 uppercase tracking-wider font-mono">
          Multi-Agent Synthesis Engine
        </h2>
      </div>
      <p className="text-xs text-zinc-500 leading-relaxed font-sans">
        Smart Solve executes a dual-loop deliberate agentic reasoning flow: analysis (Investigate & Note) and solve (Plan, Solve, Check, and Format) targets, dynamically selecting tier models.
      </p>
      <div className="grid gap-2.5 sm:grid-cols-3 pt-2">
        {DEFAULT_PROMPTS.map((p, i) => (
          <div
            key={i}
            onClick={() => onSelectPrompt(p)}
            className="rounded-lg border border-zinc-900 hover:border-zinc-800 bg-zinc-950/40 p-3 text-[11px] text-zinc-500 hover:text-zinc-350 cursor-pointer transition select-none"
          >
            {p}
          </div>
        ))}
      </div>
    </div>
  );
}
