"use client";

import { useState } from "react";
import { FileSearch, Loader2, Plus, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const TOPICS = [
  "Explain quantum entanglement",
  "Summarize recent advances in LLMs",
  "Compare renewable energy sources",
];

export default function ResearchPage() {
  const [topic, setTopic] = useState("");
  const [running, setRunning] = useState(false);

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Deep Research
        </h1>
        <p className="text-sm text-zinc-500">
          Multi-phase research pipeline: Plan &rarr; Research &rarr; Report.
          Automatically breaks your topic into sub-questions and researches each
          in parallel (max 5 concurrent).
        </p>
      </div>

      {/* How it works */}
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { phase: "1. Plan", desc: "Decompose topic into sub-questions" },
          { phase: "2. Research", desc: "Investigate each sub-question" },
          { phase: "3. Report", desc: "Synthesize findings into report" },
        ].map((p) => (
          <div
            key={p.phase}
            className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3"
          >
            <p className="text-xs font-semibold text-indigo-400">{p.phase}</p>
            <p className="mt-1 text-xs text-zinc-500">{p.desc}</p>
          </div>
        ))}
      </div>

      {/* Topic input */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="flex items-center gap-2 mb-3">
          <FileSearch className="h-4 w-4 text-zinc-500" />
          <span className="text-sm font-medium text-zinc-300">
            Start a research session
          </span>
        </div>

        <div className="flex gap-2">
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="What would you like to research?"
            disabled={running}
            className="flex-1 rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
          />
          <button
            onClick={() => setRunning(true)}
            disabled={running || !topic.trim()}
            className="flex items-center gap-1.5 rounded-md bg-zinc-100 px-4 py-2 text-xs font-semibold text-zinc-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {running ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5" />
                Start
              </>
            )}
          </button>
        </div>

        {/* Quick topics */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {TOPICS.map((t) => (
            <button
              key={t}
              onClick={() => setTopic(t)}
              disabled={running}
              className="flex items-center gap-1 rounded-full border border-zinc-800 bg-zinc-900/60 px-2.5 py-1 text-[11px] text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-300 disabled:opacity-40"
            >
              <Plus className="h-3 w-3" />
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Empty state */}
      {!running && (
        <div className="rounded-lg border border-zinc-800/50 bg-zinc-900/20 p-8 text-center">
          <p className="text-sm text-zinc-600">
            No active research sessions. Start one above.
          </p>
        </div>
      )}

      {running && (
        <div className="rounded-lg border border-amber-900/50 bg-amber-900/10 p-6 text-center">
          <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-amber-500" />
          <p className="text-sm text-amber-300">
            Research pipeline would start here. Connect the backend to run.
          </p>
          <Badge variant="yellow" className="mt-2">
            POST /api/v1/research
          </Badge>
        </div>
      )}
    </div>
  );
}
