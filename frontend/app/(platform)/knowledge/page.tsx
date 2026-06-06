"use client";

import { useEffect, useState, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import {
  fetchKnowledgeBases,
  deleteKnowledgeBase,
  createKnowledgeBase,
  type KnowledgeBase,
} from "@/lib/knowledge";
import { Trash2, Database, FolderOpen, RefreshCw, CheckCircle2, Loader2, Plus, AlertCircle } from "lucide-react";
import Link from "next/link";

export default function KnowledgePage() {
  const [bases, setBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [newKbName, setNewKbName] = useState("");
  const [creating, setCreating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const data = await fetchKnowledgeBases();
    setBases(data ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreateKb = async (e: React.FormEvent) => {
    e.preventDefault();
    const sanitized = newKbName.trim().replace(/[^a-zA-Z0-9_-]/g, "_");
    if (!sanitized) return;
    setCreating(true);
    setErrorMsg(null);
    try {
      const res = await createKnowledgeBase(sanitized);
      if (res) {
        setSuccessMsg(`Successfully created Knowledge Base: ${res.name}`);
        setNewKbName("");
        load();
        setTimeout(() => setSuccessMsg(null), 3000);
      } else {
        setErrorMsg("Failed to create Knowledge Base. Make sure backend is running.");
        setTimeout(() => setErrorMsg(null), 4000);
      }
    } catch {
      setErrorMsg("An unexpected error occurred.");
      setTimeout(() => setErrorMsg(null), 4000);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Are you sure you want to permanently delete knowledge base "${name}"? This will delete all indexed documents and vector embeddings.`)) {
      return;
    }
    setDeleting(name);
    const ok = await deleteKnowledgeBase(name);
    if (ok) {
      setBases((prev) => prev.filter((b) => b.name !== name));
      setSuccessMsg(`Successfully deleted Knowledge Base: ${name}`);
      setTimeout(() => setSuccessMsg(null), 3000);
    }
    setDeleting(null);
  };

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto w-full select-none">
      
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-900 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Database className="h-6 w-6 text-indigo-500" />
            Knowledge Bases
          </h1>
          <p className="text-sm text-zinc-400 mt-1 font-sans">
            Manage document indexing scopes. Ingested files compile a vectorless PageIndex tree and hybrid vector embedding spaces.
          </p>
        </div>

        <button
          onClick={load}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-850 hover:text-white transition shadow-sm w-fit"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Dynamic welcome context box */}
      <div className="rounded-xl border border-zinc-900 bg-zinc-950 p-5 space-y-3 shadow-inner">
        <div className="flex items-start gap-3">
          <FolderOpen className="mt-0.5 h-5 w-5 shrink-0 text-indigo-400" />
          <div className="text-xs text-zinc-450 leading-relaxed font-sans select-text">
            <p className="font-bold text-zinc-250 uppercase tracking-wider font-mono text-[10px]">
              Local Semantic Indexing
            </p>
            <p className="mt-1">
              Adding documents triggers dual indexing pipelines: **PageIndex tree hierarchy** (deliberate structural JSON summaries, ideal for vectorless tree search reasoning) and **Vector similarity spaces** (character chunks, perfect for hybrid semantic lookup). Everything remains 100% offline.
            </p>
          </div>
        </div>
      </div>

      {/* Create Knowledge Base Scope (Database) Inline Card */}
      <div className="rounded-xl border border-zinc-900 bg-zinc-950 p-5 shadow-inner">
        <div className="flex items-center gap-2 text-indigo-400 mb-4 select-none">
          <Database className="h-4.5 w-4.5" />
          <h3 className="text-xs font-extrabold uppercase font-mono tracking-wider text-zinc-350">
            Create New Database Scope
          </h3>
        </div>

        <form onSubmit={handleCreateKb} className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative">
            <input
              type="text"
              placeholder="e.g. quantum_physics, machine_learning_v2..."
              value={newKbName}
              onChange={(e) => setNewKbName(e.target.value)}
              aria-label="New knowledge base name"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans"
            />
            {newKbName.trim() && (
              <span className="absolute right-3 top-3 text-[9px] font-mono text-zinc-500 uppercase">
                Will compile as: {newKbName.trim().replace(/[^a-zA-Z0-9_-]/g, "_")}
              </span>
            )}
          </div>

          <button
            type="submit"
            disabled={creating || !newKbName.trim()}
            className="flex items-center justify-center gap-1.5 rounded-lg bg-zinc-100 px-5 py-2.5 text-xs font-bold text-zinc-900 transition-all hover:bg-white hover:shadow-[0_0_15px_rgba(255,255,255,0.15)] disabled:cursor-not-allowed disabled:opacity-40 select-none shrink-0"
          >
            {creating ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Compiling...</span>
              </>
            ) : (
              <>
                <Plus className="h-3.5 w-3.5" />
                <span>Create Database</span>
              </>
            )}
          </button>
        </form>

        {errorMsg && (
          <div className="mt-3 flex items-center gap-2 text-xs text-red-400 select-none font-sans">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {/* Grid listing */}
      {loading ? (
        <div className="rounded-xl border border-dashed border-zinc-900 p-12 text-center text-xs text-zinc-600 font-mono">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-400 mx-auto mb-3" />
          <span>Loading knowledge bases...</span>
        </div>
      ) : bases.length === 0 ? (
        <div className="rounded-xl border border-dashed border-zinc-900 p-12 text-center bg-zinc-950/10">
          <Database className="mx-auto mb-3 h-10 w-10 text-zinc-850 animate-pulse" />
          <h3 className="text-xs font-bold text-zinc-400 uppercase tracking-wider font-mono">No Knowledge Bases Found</h3>
          <p className="text-xs text-zinc-600 mt-1 max-w-xs mx-auto leading-relaxed">
            Create your first Knowledge Base scope by going to the{" "}
            <Link href="/documents" className="text-indigo-400 hover:text-indigo-300 underline font-semibold">
              Library Node
            </Link>{" "}
            and uploading files.
          </p>
        </div>
      ) : (
        <div className="grid gap-3.5 sm:grid-cols-2">
          {bases.map((kb) => (
            <div
              key={kb.name}
              className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-4.5 space-y-3.5 transition duration-300 hover:border-zinc-800 shadow-inner relative flex flex-col justify-between"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); window.location.href = '/documents'; } }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="h-8 w-8 rounded-lg bg-indigo-650/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
                    <Database className="h-4.5 w-4.5 animate-pulse" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-bold text-zinc-200 truncate select-text">{kb.name}</p>
                    <p className="text-[10px] font-mono text-zinc-400 mt-0.5">
                      {kb.total_docs} doc{kb.total_docs !== 1 ? "s" : ""} &bull; {kb.total_pages} page{kb.total_pages !== 1 ? "s" : ""}
                    </p>
                  </div>
                </div>

                <Badge variant="green" className="text-[9px] font-mono font-bold uppercase select-none">
                  {kb.status}
                </Badge>
              </div>

              {/* Action list */}
              <div className="flex items-center justify-between border-t border-zinc-900/60 pt-3 select-none">
                <Link
                  href="/documents"
                  className="flex items-center gap-1 text-[10px] font-mono font-bold text-indigo-400/90 hover:text-indigo-300 transition"
                >
                  <FolderOpen className="h-3.5 w-3.5" />
                  <span>VIEW DOCUMENTS</span>
                </Link>

                <button
                  onClick={() => handleDelete(kb.name)}
                  disabled={deleting === kb.name}
                  className="rounded p-1.5 border border-zinc-900 hover:border-zinc-800 hover:bg-zinc-900/40 text-zinc-500 hover:text-red-400 transition cursor-pointer disabled:opacity-30"
                  title="Delete Knowledge Base"
                >
                  {deleting === kb.name ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Global alert toast banners */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 select-none pointer-events-none max-w-sm" role="status" aria-live="polite">
        {successMsg && (
          <div className="rounded-lg border border-emerald-900 bg-emerald-950/80 backdrop-blur-md px-4 py-3 text-xs text-emerald-400 flex items-center gap-2 pointer-events-auto shadow-lg">
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}
      </div>

    </div>
  );
}
