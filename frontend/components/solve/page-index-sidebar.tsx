"use client";

import { Layers, Search, X, Loader2 } from "lucide-react";
import type { IndexNode } from "@/types/api";
import { TreeItem } from "./tree-item";

interface PageIndexSidebarProps {
  tree: IndexNode | null;
  loadingTree: boolean;
  selectedDocId: string;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  filteredTree: IndexNode | null;
}

export function PageIndexSidebar({
  tree,
  loadingTree,
  selectedDocId,
  searchQuery,
  onSearchChange,
  filteredTree,
}: PageIndexSidebarProps) {
  return (
    <aside className="w-80 shrink-0 border-l border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
      <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
        <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
          <Layers className="h-4 w-4 text-indigo-400 animate-pulse" />
          Reasoning Index
        </span>
      </div>

      <div className="p-3 border-b border-zinc-900/60">
        <div className="relative flex items-center border border-zinc-900 bg-zinc-950 rounded-lg p-1.5">
          <Search className="h-3.5 w-3.5 text-zinc-600 ml-1 shrink-0" />
          <input
            type="text"
            placeholder="Search index headings..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search index headings"
            className="flex-1 bg-transparent border-0 px-2 py-0 text-xs text-zinc-300 placeholder-zinc-700 focus:outline-none focus:ring-0"
          />
          {searchQuery && (
            <button onClick={() => onSearchChange("")} aria-label="Clear search" className="text-zinc-600 hover:text-zinc-400">
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3.5 space-y-1">
        {loadingTree ? (
          <div className="flex flex-col items-center justify-center py-12 text-zinc-600 text-xs gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
            <span>Loading index tree...</span>
          </div>
        ) : !selectedDocId ? (
          <div className="rounded-lg border border-dashed border-zinc-900 p-6 text-center text-zinc-500 text-xs">
            Select a document from left panel to view index tree.
          </div>
        ) : !tree ? (
          <div className="rounded-lg border border-dashed border-zinc-900 p-6 text-center text-zinc-500 text-xs">
            PageIndex tree unavailable for this document.
          </div>
        ) : filteredTree ? (
          <div className="space-y-0.5 pr-1">
            <TreeItem node={filteredTree} depth={0} />
          </div>
        ) : (
          <div className="text-center py-8 text-zinc-600 text-xs">
            No matching headings found.
          </div>
        )}
      </div>

      <div className="p-4 border-t border-zinc-900 bg-zinc-950/40 text-[10px] text-zinc-500 font-mono">
        PageIndex Explorer
      </div>
    </aside>
  );
}
