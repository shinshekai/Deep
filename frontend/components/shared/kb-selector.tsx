"use client";

import { Database } from "lucide-react";

interface KbSelectorProps {
  kbOptions: { value: string; label: string }[];
  selectedKb: string;
  onSelect: (kb: string) => void;
  disabled?: boolean;
}

export function KbSelector({ kbOptions, selectedKb, onSelect, disabled }: KbSelectorProps) {
  return (
    <div className="space-y-2">
      <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
        Active Knowledge Base
      </label>
      <div className="flex items-center gap-1.5 bg-zinc-950 border border-zinc-900 rounded-lg px-2.5 py-1">
        <Database className="h-3.5 w-3.5 text-zinc-500" />
        <select
          value={selectedKb}
          onChange={(e) => onSelect(e.target.value)}
          disabled={disabled}
          aria-label="Select active knowledge base"
          className="bg-transparent border-0 text-xs font-semibold text-zinc-300 focus:outline-none focus:ring-0 cursor-pointer w-full"
        >
          {kbOptions.length === 0 ? (
            <option value="">No KBs (Upload to create)</option>
          ) : (
            kbOptions.map((o) => (
              <option key={o.value} value={o.value} className="bg-zinc-950 text-zinc-300">
                {o.label || "(none)"}
              </option>
            ))
          )}
        </select>
      </div>
    </div>
  );
}
