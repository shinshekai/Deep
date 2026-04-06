"use client";

import { FileText } from "lucide-react";
import type { Citation } from "@/types/api";

interface CitationListProps {
  citations: Citation[];
}

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) return null;

  return (
    <div>
      <div className="mb-2 text-xs font-semibold text-zinc-500 uppercase tracking-wider">
        Citations ({citations.length})
      </div>
      <div className="flex flex-wrap gap-2">
        {citations.map((c, i) => (
          <div
            key={i}
            className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-1.5 text-xs"
          >
            <FileText className="h-3 w-3 text-zinc-500" />
            <span className="text-zinc-300">{c.doc_id}</span>
            <span className="text-zinc-600">p.{c.page}</span>
            {c.section && (
              <span className="text-zinc-500 truncate max-w-[120px]">
                {c.section}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
