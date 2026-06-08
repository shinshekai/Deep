"use client";

import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { FileText } from "lucide-react";
import type { IndexNode } from "@/types/api";

interface DocumentInfo {
  doc_id: string;
  page_count?: number;
  status: "indexed" | "processing" | "failed";
  tree?: IndexNode;
}

interface DocumentListProps {
  documents: DocumentInfo[];
  onViewTree?: (docId: string) => void;
}

export function DocumentList({ documents, onViewTree }: DocumentListProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: documents.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50,
    overscan: 5,
  });

  if (documents.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-8 text-center">
        <FileText className="mx-auto mb-3 h-8 w-8 text-zinc-700" />
        <p className="text-sm text-zinc-500">
          No documents in this knowledge base yet.
        </p>
      </div>
    );
  }

  return (
    <div
      ref={parentRef}
      className="h-[600px] overflow-auto"
      style={{ contain: "strict" }}
    >
      <div
        className="space-y-1"
        style={{ height: virtualizer.getTotalSize(), position: "relative" }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const doc = documents[virtualRow.index];
          return (
            <div
              key={doc.doc_id}
              className="flex items-center justify-between rounded-lg border border-zinc-800/60 bg-zinc-900/30 px-4 py-2.5"
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <div className="flex items-center gap-3">
                <FileText className="h-4 w-4 text-zinc-500" />
                <div>
                  <p className="text-sm text-zinc-300">{doc.doc_id}</p>
                  {doc.page_count != null && (
                    <p className="text-xs text-zinc-600">
                      {doc.page_count} pages
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`h-2 w-2 rounded-full ${
                    doc.status === "indexed"
                      ? "bg-emerald-500"
                      : doc.status === "processing"
                        ? "animate-pulse bg-amber-500"
                        : "bg-red-500"
                  }`}
                />
                <span className="text-xs text-zinc-500 capitalize">
                  {doc.status}
                </span>
                {doc.status === "indexed" && onViewTree && (
                  <button
                    onClick={() => onViewTree(doc.doc_id)}
                    aria-label="Toggle document tree view"
                    className="rounded px-2 py-0.5 text-xs text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
                  >
                    Tree
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
