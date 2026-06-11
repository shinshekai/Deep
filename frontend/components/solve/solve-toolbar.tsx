"use client";

import { PanelLeft, PanelRight } from "lucide-react";

interface SolveToolbarProps {
  showLeftSidebar: boolean;
  showRightSidebar: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onReset: () => void;
  canReset: boolean;
}

export function SolveToolbar({
  showLeftSidebar,
  showRightSidebar,
  onToggleLeft,
  onToggleRight,
  onReset,
  canReset,
}: SolveToolbarProps) {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-900 bg-zinc-950/40 px-4 select-none">
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleLeft}
          className={`p-1.5 rounded-lg border transition ${
            showLeftSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
          }`}
          aria-label="Toggle sources sidebar"
          aria-expanded={showLeftSidebar}
        >
          <PanelLeft className="h-4 w-4" />
        </button>
        <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
        <span className="text-xs font-semibold text-zinc-250 font-mono">Smart Solve Mission Ingest</span>
      </div>

      <div className="flex items-center gap-2">
        {canReset && (
          <button
            onClick={onReset}
            className="flex items-center gap-1 rounded bg-zinc-900 hover:bg-zinc-800/80 px-2 py-1 text-xs text-zinc-400 transition"
            aria-label="Reset solve session"
          >
            Reset Solve
          </button>
        )}
        <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
        <button
          onClick={onToggleRight}
          className={`p-1.5 rounded-lg border transition ${
            showRightSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
          }`}
          aria-label="Toggle index tree sidebar"
          aria-expanded={showRightSidebar}
        >
          <PanelRight className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
