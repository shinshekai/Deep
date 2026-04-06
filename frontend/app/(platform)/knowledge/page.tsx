"use client";

import { useEffect, useState, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import {
  fetchKnowledgeBases,
  deleteKnowledgeBase,
  type KnowledgeBase,
} from "@/lib/knowledge";
import { Trash2, Database, FolderOpen } from "lucide-react";

export default function KnowledgePage() {
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const data = await fetchKnowledgeBases();
    setBases(data ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleDelete = async (name: string) => {
    setDeleting(name);
    const ok = await deleteKnowledgeBase(name);
    if (ok) {
      setBases((prev) => prev.filter((b) => b.name !== name));
    }
    setDeleting(null);
  };

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Knowledge Bases
        </h1>
        <p className="text-sm text-zinc-500">
          Manage document collections. Upload creates a Knowledge Base
          with PageIndex tree (vectorless retrieval) and an optional vector
          embeddings store.
        </p>
      </div>

      {/* Create KB hint */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="flex items-start gap-3">
          <FolderOpen className="mt-0.5 h-5 w-5 shrink-0 text-zinc-500" />
          <div className="text-sm text-zinc-400">
            <p className="font-medium text-zinc-300">
              How Knowledge Bases work
            </p>
            <p className="mt-1">
              Upload PDF/TXT/MD files to create a KB. The system builds a
              hierarchical PageIndex tree (<span className="text-zinc-500">fast, vectorless</span>)
              and an optional vector KB for hybrid retrieval. Each upload
              triggers parallel processing with progress tracking.
            </p>
          </div>
        </div>
      </div>

      {/* KB list */}
      {loading ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-8 text-center text-sm text-zinc-600">
          Loading knowledge bases...
        </div>
      ) : bases.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-8 text-center">
          <Database className="mx-auto mb-3 h-8 w-8 text-zinc-700" />
          <p className="text-sm text-zinc-500">
            No knowledge bases yet. Upload a document to{" "}
            <a href="/documents" className="text-indigo-400 underline">
              create one
            </a>
            .
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {bases.map((kb) => (
            <div
              key={kb.name}
              className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-3"
            >
              <div className="flex items-center gap-3">
                <Database className="h-4 w-4 text-zinc-500" />
                <div>
                  <p className="text-sm font-medium text-zinc-200">{kb.name}</p>
                  <p className="text-xs text-zinc-600">
                    {kb.total_docs} doc{kb.total_docs !== 1 ? "s" : ""} ·{" "}
                    {kb.total_pages} page{kb.total_pages !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="green" dot>
                  {kb.status}
                </Badge>
                <button
                  onClick={() => handleDelete(kb.name)}
                  disabled={deleting === kb.name}
                  className="rounded p-1.5 text-zinc-600 transition-colors hover:bg-zinc-800 hover:text-red-400 disabled:opacity-30"
                  title="Delete KB"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={load}
        className="self-start rounded bg-zinc-800 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
      >
        Refresh
      </button>
    </div>
  );
}
