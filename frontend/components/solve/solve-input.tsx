"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Send, Database, Layers, ArrowRightLeft } from "lucide-react";
import type { SolveQuery } from "@/types/api";
import { API_BASE_URL, secureFetch } from "@/lib/config";

interface SolveInputProps {
  onSend: (query: SolveQuery) => void;
  isStreaming: boolean;
}

export function SolveInput({ onSend, isStreaming }: SolveInputProps) {
  const [text, setText] = useState("");
  const [kbName, setKbName] = useState("");
  const [mode, setMode] = useState<SolveQuery["mode"]>("auto");
  const [retrieval, setRetrieval] = useState<SolveQuery["retrieval_pipeline"]>("tree");
  const [kbOptions, setKbOptions] = useState<{ value: string; label: string }[]>([
    { value: "", label: "(none)" }
  ]);

  // Dynamically load active Knowledge Bases from backend
  useEffect(() => {
    async function loadKbs() {
      try {
        const response = await secureFetch(`${API_BASE_URL}/knowledge/bases`);
        if (response.ok) {
          const list = await response.json();
          if (Array.isArray(list)) {
            const mapped = list.map((kb: unknown) => {
              const name = typeof kb === "string" ? kb : (kb && typeof kb === "object" && "name" in kb ? String(kb.name) : "default");
              return { value: name, label: name };
            });
            setKbOptions([{ value: "", label: "(none)" }, ...mapped]);
            if (mapped.length > 0) {
              setKbName(mapped[0].value); // Select first KB as default
            }
          }
        }
      } catch (e) {
        console.error("Failed to load knowledge bases", e);
      }
    }
    loadKbs();
  }, []);

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
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 rounded-xl border border-zinc-900 bg-zinc-950/60 p-4 shadow-lg">
      
      {/* Floating Intelligence Composer Textarea */}
      <div className="relative">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask DEEP anything about your document workspace..."
          disabled={isStreaming}
          rows={4}
          aria-label="Ask DEEP anything about your document workspace"
          className="w-full rounded-lg border border-zinc-900 bg-zinc-950/20 px-4 py-3.5 text-sm text-zinc-100 placeholder-zinc-700 caret-indigo-500 focus:border-indigo-600 focus:outline-none focus:ring-0 disabled:opacity-50 resize-none font-sans leading-relaxed"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
        />
        {isStreaming && (
          <div className="absolute inset-0 bg-zinc-950/40 backdrop-blur-[1px] flex items-center justify-center rounded-lg text-xs font-semibold text-zinc-500 font-mono tracking-widest uppercase">
            Agent Solvers Active...
          </div>
        )}
      </div>

      {/* Dynamic Controls Bar */}
      <div className="flex flex-wrap items-center gap-2.5 pt-2 border-t border-zinc-900/60">
        
        {/* KB Selection Selector with Database Icon */}
        <div className="flex items-center gap-1.5 bg-zinc-950 border border-zinc-900 rounded-lg px-2.5 py-1">
          <Database className="h-3.5 w-3.5 text-zinc-500" />
          <select
            value={kbName}
            onChange={(e) => setKbName(e.target.value)}
            disabled={isStreaming}
            aria-label="Select knowledge base"
            className="bg-transparent border-0 text-xs font-semibold text-zinc-300 focus:outline-none focus:ring-0 cursor-pointer"
          >
            {kbOptions.map((o) => (
              <option key={o.value} value={o.value} className="bg-zinc-950 text-zinc-300">
                {o.label || "No Workspace"}
              </option>
            ))}
          </select>
        </div>

        {/* Solver Mode Select */}
        <div className="flex items-center gap-1.5 bg-zinc-950 border border-zinc-900 rounded-lg px-2.5 py-1">
          <Layers className="h-3.5 w-3.5 text-zinc-500" />
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as SolveQuery["mode"])}
            disabled={isStreaming}
            aria-label="Select solver mode"
            className="bg-transparent border-0 text-xs font-semibold text-zinc-300 focus:outline-none focus:ring-0 cursor-pointer"
          >
            <option value="auto" className="bg-zinc-950 text-zinc-300">Auto Mode</option>
            <option value="detailed" className="bg-zinc-950 text-zinc-300">Detailed Reason</option>
            <option value="quick" className="bg-zinc-950 text-zinc-300">Quick synthesis</option>
          </select>
        </div>

        {/* Retrieval Pipeline Mode Select */}
        <div className="flex items-center gap-1.5 bg-zinc-950 border border-zinc-900 rounded-lg px-2.5 py-1">
          <ArrowRightLeft className="h-3.5 w-3.5 text-zinc-500" />
          <select
            value={retrieval}
            onChange={(e) => setRetrieval(e.target.value as SolveQuery["retrieval_pipeline"])}
            disabled={isStreaming}
            aria-label="Select retrieval pipeline"
            className="bg-transparent border-0 text-xs font-semibold text-zinc-300 focus:outline-none focus:ring-0 cursor-pointer font-mono"
          >
            <option value="tree" className="bg-zinc-950 text-zinc-300">PageIndex Tree</option>
            <option value="hybrid" className="bg-zinc-950 text-zinc-300">Hybrid (Vec+Key)</option>
            <option value="naive" className="bg-zinc-950 text-zinc-300">Naive Vector</option>
            <option value="combined" className="bg-zinc-950 text-zinc-300">Combined Pipe</option>
          </select>
        </div>

        {/* Action Trigger Button */}
        <div className="ml-auto">
          <button
            type="submit"
            aria-disabled={disabled}
            onClick={(e) => {
              if (disabled) {
                e.preventDefault();
              }
            }}
            aria-label="Run solve mission"
            className={`flex items-center gap-1.5 rounded-lg px-4.5 py-2 text-xs font-bold transition duration-300 shadow-md ${
              disabled
                ? "bg-zinc-900 text-zinc-650 cursor-not-allowed border border-transparent"
                : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/10 cursor-pointer border border-indigo-500/20"
            }`}
          >
            <Send className="h-3.5 w-3.5" />
            {isStreaming ? "Solving..." : "Solve Mission"}
          </button>
        </div>

      </div>

    </form>
  );
}
