"use client";

import { useState, type FormEvent } from "react";
import { Send } from "lucide-react";
import type { SolveQuery } from "@/types/api";

const KB_OPTIONS = [
  { value: "", label: "(none)" },
  { value: "default", label: "Default" },
];

interface SolveInputProps {
  onSend: (query: SolveQuery) => void;
  isStreaming: boolean;
}

export function SolveInput({ onSend, isStreaming }: SolveInputProps) {
  const [text, setText] = useState("");
  const [kbName, setKbName] = useState("");
  const [mode, setMode] = useState<SolveQuery["mode"]>("auto");
  const [retrieval, setRetrieval] = useState<SolveQuery["retrieval_pipeline"]>("tree");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim() || isStreaming) return;
    onSend({
      query: text.trim(),
      kb_name: kbName,
      mode,
      retrieval_pipeline: retrieval,
    });
  };

  const disabled = isStreaming || !text.trim();

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      {/* Query textarea */}
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Ask a question about your documents..."
        disabled={isStreaming}
        rows={4}
        className="w-full rounded-lg border border-zinc-800 bg-zinc-900/80 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 caret-zinc-400 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50 resize-none"
      />

      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={kbName}
          onChange={(e) => setKbName(e.target.value)}
          disabled={isStreaming}
          className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-600"
        >
          {KB_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              KB: {o.label}
            </option>
          ))}
        </select>

        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as SolveQuery["mode"])}
          disabled={isStreaming}
          className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-600"
        >
          <option value="auto">Auto Mode</option>
          <option value="detailed">Detailed</option>
          <option value="quick">Quick</option>
        </select>

        <select
          value={retrieval}
          onChange={(e) => setRetrieval(e.target.value as SolveQuery["retrieval_pipeline"])}
          disabled={isStreaming}
          className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-600"
        >
          <option value="tree">Tree Retrieval</option>
          <option value="hybrid">Hybrid</option>
          <option value="naive">Naive</option>
          <option value="combined">Combined</option>
        </select>

        <div className="ml-auto">
          <button
            type="submit"
            disabled={disabled}
            className="flex items-center gap-1.5 rounded-md bg-zinc-100 px-4 py-1.5 text-xs font-semibold text-zinc-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send className="h-3.5 w-3.5" />
            {isStreaming ? "Solving..." : "Solve"}
          </button>
        </div>
      </div>
    </form>
  );
}
