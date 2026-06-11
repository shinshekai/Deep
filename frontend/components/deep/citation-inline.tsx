"use client"

import { clsx } from "clsx"
import { FileText, ExternalLink } from "lucide-react"
import type { Citation } from "@/types/api"

interface CitationInlineProps {
  citation: Citation
  index?: number
}

export function CitationInline({ citation, index }: CitationInlineProps) {
  return (
    <span className="relative inline-flex group/clip">
      <span className="inline-flex items-center gap-1 rounded-md border border-indigo-900/30 bg-indigo-950/10 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-indigo-400 cursor-pointer hover:bg-indigo-950/20 transition-colors">
        <FileText className="h-2.5 w-2.5" />
        {index !== undefined ? `[${index + 1}]` : citation.doc_id?.slice(0, 8)}
      </span>

      {/* Hover tooltip */}
      <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 opacity-0 group-hover/clip:opacity-100 transition-opacity z-50">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 shadow-xl min-w-[200px]">
          <div className="text-xs font-semibold text-zinc-200 mb-1">
            {citation.section || "Source"}
          </div>
          <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
            <span>Doc: {citation.doc_id?.slice(0, 12)}</span>
            {citation.page != null && <span>Page {citation.page}</span>}
          </div>
          <div className="mt-1.5 flex items-center gap-1 text-[10px] text-indigo-400">
            <ExternalLink className="h-2.5 w-2.5" />
            <span>View source</span>
          </div>
        </div>
      </div>
    </span>
  )
}

interface CitationListProps {
  citations: Citation[]
}

export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1.5">
      {citations.map((c, i) => (
        <CitationInline key={i} citation={c} index={i} />
      ))}
    </div>
  )
}
