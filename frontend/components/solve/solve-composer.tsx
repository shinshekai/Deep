"use client";

import { useState } from "react";
import { ArrowRightLeft, Layers, Zap, Info, ChevronDown, ChevronRight } from "lucide-react";
import type { SolveQuery } from "@/types/api";

const COLLABORATION_PATTERNS = [
  {
    name: "Sequential",
    description: "Agents execute in a fixed pipeline order: Investigate → Annotate → Plan → Solve → Check → Format. Each agent receives the accumulated context from prior stages.",
  },
  {
    name: "Mixture of Experts",
    description: "Multiple specialist agents process the query in parallel. Results are weighted by confidence scores and merged via a router agent.",
  },
  {
    name: "Deliberation",
    description: "Agents engage in multi-round debate. A proposal is generated, critiqued, revised, and re-critiqued until convergence or a round budget is exhausted.",
  },
  {
    name: "Distillation",
    description: "A large teacher model produces a comprehensive reasoning trace. A smaller student model then learns to replicate the output, reducing inference cost for similar future queries.",
  },
];

interface SolveComposerProps {
  text: string;
  onTextChange: (text: string) => void;
  mode: SolveQuery["mode"];
  onModeChange: (mode: SolveQuery["mode"]) => void;
  retrieval: SolveQuery["retrieval_pipeline"];
  onRetrievalChange: (pipeline: SolveQuery["retrieval_pipeline"]) => void;
  onSend: () => void;
}

export function SolveComposer({
  text,
  onTextChange,
  mode,
  onModeChange,
  retrieval,
  onRetrievalChange,
  onSend,
}: SolveComposerProps) {
  const [showPatterns, setShowPatterns] = useState(false);
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="rounded-xl border border-zinc-900 bg-zinc-950 p-4 space-y-4 shadow-lg select-none">
      <textarea
        value={text}
        onChange={(e) => onTextChange(e.target.value)}
        placeholder="Ask conceptual questions about your sources..."
        rows={4}
        aria-label="Ask conceptual questions about your sources"
        className="w-full rounded-lg border border-zinc-900 bg-zinc-950/20 px-3 py-2 text-xs md:text-sm text-zinc-100 placeholder-zinc-700 focus:outline-none focus:border-indigo-650 font-sans leading-relaxed resize-none"
        onKeyDown={handleKeyDown}
      />

      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-zinc-900/60">
        <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-900 rounded-lg px-2 py-1 text-zinc-400 text-[10px]">
          <ArrowRightLeft className="h-3 w-3 text-zinc-400" />
          <select
            value={retrieval}
            onChange={(e) => onRetrievalChange(e.target.value as SolveQuery["retrieval_pipeline"])}
            aria-label="Select retrieval pipeline"
            className="bg-transparent border-0 p-0 text-[10px] font-semibold text-zinc-300 focus:outline-none cursor-pointer"
          >
            <option value="tree">PageIndex Tree</option>
            <option value="hybrid">Hybrid (Vec+Key)</option>
            <option value="naive">Naive Vector</option>
            <option value="combined">Combined Pipeline</option>
          </select>
        </div>

        <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-900 rounded-lg px-2 py-1 text-zinc-400 text-[10px]">
          <Layers className="h-3 w-3 text-zinc-400" />
          <select
            value={mode}
            onChange={(e) => onModeChange(e.target.value as SolveQuery["mode"])}
            aria-label="Select solver mode"
            className="bg-transparent border-0 p-0 text-[10px] font-semibold text-zinc-300 focus:outline-none cursor-pointer"
          >
            <option value="auto">Auto Mode</option>
            <option value="detailed">Detailed Loop</option>
            <option value="quick">Quick Synthesis</option>
          </select>
        </div>

        <button
          onClick={onSend}
          disabled={!text.trim()}
          aria-label="Run solve mission"
          className="ml-auto flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white font-bold text-xs px-4 py-2 transition"
        >
          <Zap className="h-3.5 w-3.5" />
          <span>Run Solve Mission</span>
        </button>
      </div>

      <button
        type="button"
        onClick={() => setShowPatterns(!showPatterns)}
        className="flex items-center gap-1.5 text-[10px] text-zinc-500 hover:text-zinc-300 transition pt-1"
      >
        {showPatterns ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <Info className="h-3 w-3" />
        Agent Collaboration Patterns
      </button>

      {showPatterns && (
        <div className="grid gap-2 pt-1">
          {COLLABORATION_PATTERNS.map((p) => (
            <div key={p.name} className="rounded-lg border border-zinc-900 bg-zinc-950/40 px-3 py-2">
              <div className="text-[10px] font-bold text-zinc-300 uppercase tracking-wider font-mono">{p.name}</div>
              <p className="text-[10px] text-zinc-500 mt-0.5 leading-relaxed">{p.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
