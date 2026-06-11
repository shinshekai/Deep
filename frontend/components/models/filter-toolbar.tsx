"use client";

import { Search } from "lucide-react";

interface FilterToolbarProps {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  selectedParamCat: string;
  onParamCatChange: (cat: string) => void;
}

export function FilterToolbar({ searchQuery, onSearchChange, selectedParamCat, onParamCatChange }: FilterToolbarProps) {
  return (
    <div className="flex flex-col gap-4 border-b border-zinc-900 pb-5 mb-6 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 className="text-lg font-bold text-white uppercase tracking-wide font-sans">Pipeline Routing Workspace</h2>
        <p className="text-xs text-zinc-400">Target models specifically to the T1, T2, or T3 pipeline slots.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search className="absolute inset-y-0 left-0 ml-2.5 h-3.5 w-3.5 text-zinc-500 self-center" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search models..."
            aria-label="Search models"
            className="h-8 rounded-lg border border-zinc-800 bg-zinc-950 pl-8 pr-3 text-xs text-white placeholder-zinc-600 focus:border-indigo-600 focus:outline-none transition w-44"
          />
        </div>

        <select
          value={selectedParamCat}
          onChange={(e) => onParamCatChange(e.target.value)}
          className="h-8 rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 text-xs text-zinc-300 focus:outline-none font-mono"
        >
          <option value="all">ALL SIZES</option>
          <option value="small">SMALL (&lt;7B)</option>
          <option value="medium">MEDIUM (7B-32B)</option>
          <option value="large">LARGE (&gt;32B)</option>
        </select>
      </div>
    </div>
  );
}
