"use client";

import type { FormEvent } from "react";
import { Send, ArrowRightLeft, Layers, AlertCircle } from "lucide-react";
import type { SolveQuery } from "@/types/api";

interface ChatInputProps {
  input: string;
  onInputChange: (value: string) => void;
  isStreaming: boolean;
  onSubmit: (e: FormEvent) => void;
  retrievalMode: SolveQuery["retrieval_pipeline"];
  onRetrievalModeChange: (mode: SolveQuery["retrieval_pipeline"]) => void;
  solveMode: SolveQuery["mode"];
  onSolveModeChange: (mode: SolveQuery["mode"]) => void;
  solveStatus: string;
}

export function ChatInput({
  input,
  onInputChange,
  isStreaming,
  onSubmit,
  retrievalMode,
  onRetrievalModeChange,
  solveMode,
  onSolveModeChange,
  solveStatus,
}: ChatInputProps) {
  return (
    <footer className="border-t border-zinc-900/80 bg-zinc-950/80 p-4 shrink-0 select-none">
      <form onSubmit={onSubmit} className="max-w-3xl mx-auto space-y-3.5">
        <div className="relative flex items-end border border-zinc-900 bg-zinc-950/30 rounded-2xl p-2 focus-within:border-zinc-800 shadow-md">
          <textarea
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            placeholder={
              isStreaming
                ? "Thinking loop running..."
                : "Ask conceptual questions about your sources..."
            }
            disabled={isStreaming}
            rows={1}
            className="flex-1 max-h-40 min-h-10 rounded-xl border-0 bg-transparent px-3 py-2 text-xs md:text-sm text-zinc-100 placeholder-zinc-700 focus:outline-none focus:ring-0 disabled:opacity-50 resize-none leading-relaxed"
            aria-label="Ask a question"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSubmit(e as unknown as FormEvent);
              }
            }}
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition duration-300 ${
              isStreaming || !input.trim()
                ? "bg-zinc-900 text-zinc-750 cursor-not-allowed"
                : "bg-indigo-650 hover:bg-indigo-650 hover:opacity-90 text-white shadow-lg shadow-indigo-600/10 cursor-pointer"
            }`}
            aria-label="Send message"
          >
            <Send className="h-4.5 w-4.5" />
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[10px]">
          <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-900 rounded-lg px-2.5 py-1 text-zinc-400">
            <ArrowRightLeft className="h-3 w-3 text-zinc-400" />
            <span className="font-mono text-[9px] uppercase text-zinc-400 mr-0.5">
              Pipe
            </span>
            <select
              value={retrievalMode}
              onChange={(e) =>
                onRetrievalModeChange(
                  e.target.value as SolveQuery["retrieval_pipeline"]
                )
              }
              className="bg-transparent border-0 p-0 text-[10px] font-semibold text-zinc-300 focus:outline-none focus:ring-0 cursor-pointer"
              aria-label="Select retrieval pipeline"
            >
              <option value="tree">PageIndex Tree</option>
              <option value="hybrid">Hybrid (Vec+Key)</option>
              <option value="naive">Naive Vector</option>
              <option value="combined">Combined Pipeline</option>
            </select>
          </div>

          <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-900 rounded-lg px-2.5 py-1 text-zinc-400">
            <Layers className="h-3 w-3 text-zinc-400" />
            <span className="font-mono text-[9px] uppercase text-zinc-400 mr-0.5">
              Mode
            </span>
            <select
              value={solveMode}
              onChange={(e) =>
                onSolveModeChange(e.target.value as SolveQuery["mode"])
              }
              className="bg-transparent border-0 p-0 text-[10px] font-semibold text-zinc-300 focus:outline-none focus:ring-0 cursor-pointer"
              aria-label="Select solve mode"
            >
              <option value="auto">Auto Model</option>
              <option value="detailed">Detailed Loop</option>
              <option value="quick">Quick Cascade</option>
            </select>
          </div>

          {solveStatus === "closed" && (
            <div className="flex items-center gap-1 text-amber-500 font-mono text-[9px] ml-auto">
              <AlertCircle className="h-3.5 w-3.5" />
              <span>WS OFFLINE</span>
            </div>
          )}
        </div>
      </form>
    </footer>
  );
}
