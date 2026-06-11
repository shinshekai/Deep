"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { IndexNode } from "@/types/api";

export function TreeItem({ node, depth = 0 }: { node: IndexNode; depth: number }) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="space-y-1 select-none">
      <div
        onClick={() => setExpanded(!expanded)}
        className={`flex items-start gap-1.5 py-1 px-2 rounded-lg text-xs transition cursor-pointer hover:bg-zinc-900/40 ${
          expanded ? "bg-zinc-900/20 text-zinc-200" : "text-zinc-450 hover:text-zinc-300"
        }`}
        style={{ paddingLeft: `${depth * 10 + 8}px` }}
        role="button"
        aria-expanded={expanded}
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(!expanded); } }}
      >
        {hasChildren ? (
          <span className="mt-0.5 shrink-0">
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </span>
        ) : (
          <span className="h-3.5 w-3.5 mt-0.5 shrink-0 flex items-center justify-center">
            <span className="h-1 w-1 rounded-full bg-zinc-700" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium truncate">{node.title || "Untitled Heading"}</span>
            {node.start_index !== undefined && (
              <span className="text-[9px] font-mono text-zinc-500 font-bold shrink-0">
                p.{node.start_index}
              </span>
            )}
          </div>
          {expanded && node.summary && (
            <p className="mt-1 text-[10px] text-zinc-500 font-sans leading-relaxed whitespace-pre-wrap select-text border-l border-zinc-800 pl-2">
              {node.summary}
            </p>
          )}
        </div>
      </div>
      {expanded && hasChildren && (
        <div className="space-y-0.5">
          {node.children.map((child, i) => (
            <TreeItem key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
