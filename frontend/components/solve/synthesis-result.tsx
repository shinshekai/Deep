"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { linkifyCitations } from "@/lib/markdown-citations";
import { Sparkles, Copy, FileText } from "lucide-react";
import { CitationList } from "./citation-list";
import type { Citation, CompleteFrame } from "@/types/api";

interface SynthesisResultProps {
  answer: CompleteFrame;
  citations: Citation[];
  onNewSession: () => void;
}

export function SynthesisResult({ answer, citations, onNewSession }: SynthesisResultProps) {
  const copyToClipboard = (txt: string) => {
    navigator.clipboard.writeText(txt);
  };

  return (
    <div className="space-y-5 animate-slide-in">
      <div className="rounded-xl border border-zinc-900 bg-zinc-950 shadow-2xl p-6 space-y-5 select-text">
        <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
          <span className="text-xs uppercase font-extrabold text-indigo-400 tracking-wider font-mono flex items-center gap-1.5 select-none">
            <Sparkles className="h-4 w-4 text-indigo-400" />
            Synthesis Output
          </span>
          <button
            onClick={() => copyToClipboard(answer.answer)}
            aria-label="Copy as markdown"
            className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-300 transition select-none"
          >
            <Copy className="h-3.5 w-3.5" />
            <span>Copy MD</span>
          </button>
        </div>

        <div className="prose prose-invert prose-xs md:prose-sm max-w-none prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-zinc-900 prose-code:text-indigo-400 leading-relaxed select-text">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {linkifyCitations(answer.answer)}
          </ReactMarkdown>
        </div>

        {citations.length > 0 && (
          <div className="pt-4 border-t border-zinc-900/60 select-none">
            <CitationList citations={citations} />
          </div>
        )}

        {answer.solve_dir && (
          <div className="flex justify-between items-center text-[10px] font-mono text-zinc-500 pt-2 border-t border-zinc-900/40 select-none">
            <span>Artifact Folder: {answer.solve_dir}</span>
            {answer.metadata && (
              <div className="flex items-center gap-3">
                <span>Elapsed: {answer.metadata.elapsed_seconds}s</span>
                <span>Score: {answer.metadata.complexity_score?.toFixed(2)}</span>
                <span className="text-indigo-400 uppercase">{answer.metadata.model_used}</span>
              </div>
            )}
          </div>
        )}
      </div>

      <button
        onClick={onNewSession}
        aria-label="Start new solve session"
        className="rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-300 font-semibold text-xs px-4 py-2 transition"
      >
        New Solve Session
      </button>
    </div>
  );
}
