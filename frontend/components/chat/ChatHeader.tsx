"use client";

import { PanelLeft, PanelRight, Trash2 } from "lucide-react";

interface ChatHeaderProps {
  showLeftSidebar: boolean;
  onToggleLeft: () => void;
  showRightSidebar: boolean;
  onToggleRight: () => void;
  hasMessages: boolean;
  onClearChat: () => void;
}

export function ChatHeader({
  showLeftSidebar,
  onToggleLeft,
  showRightSidebar,
  onToggleRight,
  hasMessages,
  onClearChat,
}: ChatHeaderProps) {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-900 bg-zinc-950/40 px-4 select-none">
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleLeft}
          className={`p-1.5 rounded-lg border transition ${
            showLeftSidebar
              ? "bg-zinc-900 border-zinc-800 text-zinc-200"
              : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
          }`}
          title="Toggle Sources Sidebar"
          aria-label="Toggle sources sidebar"
          aria-expanded={showLeftSidebar}
        >
          <PanelLeft className="h-4 w-4" />
        </button>
        <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
        <span className="text-xs font-semibold text-zinc-200 font-mono">Chat Lab</span>
      </div>

      <div className="flex items-center gap-2">
        {hasMessages && (
          <button
            onClick={onClearChat}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-900 hover:border-zinc-850 hover:bg-zinc-900/35 px-2.5 py-1 text-xs text-zinc-500 hover:text-zinc-300 transition"
            aria-label="Clear chat thread"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>Clear Thread</span>
          </button>
        )}
        <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
        <button
          onClick={onToggleRight}
          className={`p-1.5 rounded-lg border transition ${
            showRightSidebar
              ? "bg-zinc-900 border-zinc-800 text-zinc-200"
              : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
          }`}
          title="Toggle Notebook Panel"
          aria-label="Toggle notebook panel"
          aria-expanded={showRightSidebar}
        >
          <PanelRight className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
