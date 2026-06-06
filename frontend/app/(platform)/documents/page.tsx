"use client";

import { useState, useEffect, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { DocumentUpload } from "@/components/documents/document-upload";
import { DocumentList } from "@/components/documents/document-list";
import { fetchKnowledgeBases, createKnowledgeBase, type UploadTask } from "@/lib/knowledge";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import { Library, FolderPlus, Database, ShieldCheck, Loader2, RefreshCw, Plus } from "lucide-react";
import Link from "next/link";

type ActiveUpload = {
  taskId: string;
  fileName: string;
  task: UploadTask | null;
};

type DocumentInfo = {
  doc_id: string;
  page_count?: number;
  status: "indexed" | "processing" | "failed";
};

export default function DocumentsPage() {
  const [kbNames, setKbNames] = useState<string[]>([]);
  const [selectedKb, setSelectedKb] = useState("");
  const [activeUploads, setActiveUploads] = useState<ActiveUpload[]>([]);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Inline DB creation state
  const [showCreateInput, setShowCreateInput] = useState(false);
  const [newKbInput, setNewKbInput] = useState("");
  const [creatingKb, setCreatingKb] = useState(false);

  // Load available KB names
  const loadKbs = useCallback(async () => {
    const bases = await fetchKnowledgeBases();
    if (bases) {
      const names = bases.map((b) => b.name);
      setKbNames(names);
      if (names.length > 0) {
        if (!selectedKb || (!names.includes(selectedKb) && selectedKb !== "default")) {
          setSelectedKb(names[0]);
        }
      } else {
        setSelectedKb("default"); // Auto-select default so upload form is enabled
      }
    } else {
      setSelectedKb("default");
    }
  }, [selectedKb]);

  useEffect(() => {
    loadKbs();
  }, [loadKbs]);

  const handleInlineCreate = async () => {
    const sanitized = newKbInput.trim().replace(/[^a-zA-Z0-9_-]/g, "_");
    if (!sanitized) return;
    setCreatingKb(true);
    try {
      const res = await createKnowledgeBase(sanitized);
      if (res) {
        const updatedBases = await fetchKnowledgeBases();
        if (updatedBases) {
          setKbNames(updatedBases.map((b) => b.name));
        } else {
          setKbNames((prev) => [...prev, res.name]);
        }
        setSelectedKb(res.name);
        setNewKbInput("");
        setShowCreateInput(false);
      }
    } catch (err) {
      console.error("Failed to create KB inline:", err);
    } finally {
      setCreatingKb(false);
    }
  };

  // Fetch documents when selected KB changes
  const fetchDocs = useCallback(() => {
    if (!selectedKb) {
      setDocuments([]);
      return;
    }
    setLoadingDocs(true);
    secureFetch(`${API_BASE_URL}/knowledge/${selectedKb}/documents`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setDocuments(data);
        } else if (data.documents && Array.isArray(data.documents)) {
          setDocuments(data.documents);
        } else {
          setDocuments([]);
        }
      })
      .catch(() => setDocuments([]))
      .finally(() => setLoadingDocs(false));
  }, [selectedKb]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  const handleUploadStart = useCallback(
    (taskId: string, fileName: string) => {
      setActiveUploads((prev) => [
        ...prev,
        { taskId, fileName, task: null },
      ]);
    },
    []
  );

  // Poll active uploads
  useEffect(() => {
    if (activeUploads.length === 0) return;
    const interval = setInterval(async () => {
      setActiveUploads((prev) =>
        prev.filter((u) => {
          if (u.task?.status === "complete" || u.task?.status === "failed") {
            return false;
          }
          return true;
        })
      );
      // Refresh document list after uploads complete
      if (selectedKb) {
        secureFetch(`${API_BASE_URL}/knowledge/${selectedKb}/documents`)
          .then((res) => res.json())
          .then((data) => {
            if (Array.isArray(data)) setDocuments(data);
            else if (data.documents) setDocuments(data.documents);
          })
          .catch(() => {});
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [activeUploads.length, selectedKb]);

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto w-full select-none">
      
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-900 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Library className="h-6 w-6 text-indigo-500" />
            Library Node
          </h1>
          <p className="text-sm text-zinc-400 mt-1 font-sans">
            Upload and query document assets. PDF, TXT, and MD formats compile into high-fidelity local reasoning structures.
          </p>
        </div>

        <button
          onClick={fetchDocs}
          className="flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-850 hover:text-white transition shadow-sm w-fit"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh List</span>
        </button>
      </div>

      {/* Target scope card selector */}
      <div className="rounded-xl border border-zinc-900 bg-zinc-950 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-inner select-none animate-fade-in">
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <Database className="h-5 w-5 text-indigo-400 shrink-0" />
          
          {!showCreateInput ? (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs uppercase font-extrabold text-zinc-500 font-mono tracking-wider">
                Active Scope:
              </span>
              <select
                value={selectedKb}
                onChange={(e) => setSelectedKb(e.target.value)}
                className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans cursor-pointer"
              >
                {kbNames.length === 0 ? (
                  <option value="default">default (Upload creates default)</option>
                ) : (
                  kbNames.map((name) => (
                    <option key={name} value={name}>{name}</option>
                  ))
                )}
              </select>
              
              <button
                onClick={() => setShowCreateInput(true)}
                className="text-xs font-mono font-bold text-zinc-450 hover:text-indigo-400 transition ml-2 flex items-center gap-1 cursor-pointer"
              >
                <Plus className="h-3 w-3" />
                <span>[CREATE NEW]</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 w-full animate-slide-in">
              <span className="text-xs uppercase font-extrabold text-indigo-400 font-mono tracking-wider shrink-0">
                New Name:
              </span>
              <input
                type="text"
                placeholder="e.g. quantum_notes"
                value={newKbInput}
                onChange={(e) => setNewKbInput(e.target.value)}
                aria-label="Rename knowledge base"
                className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-350 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans w-32 sm:w-44"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleInlineCreate();
                  if (e.key === "Escape") {
                    setShowCreateInput(false);
                    setNewKbInput("");
                  }
                }}
              />
              <button
                onClick={handleInlineCreate}
                disabled={creatingKb || !newKbInput.trim()}
                className="rounded-lg bg-zinc-100 hover:bg-white text-zinc-900 text-xs px-2.5 py-1.5 font-bold transition disabled:opacity-40 disabled:cursor-not-allowed shrink-0 cursor-pointer"
              >
                {creatingKb ? "..." : "Add"}
              </button>
              <button
                onClick={() => {
                  setShowCreateInput(false);
                  setNewKbInput("");
                }}
                className="text-xs font-mono text-zinc-500 hover:text-zinc-300 ml-1 shrink-0 cursor-pointer"
              >
                Cancel
              </button>
            </div>
          )}
        </div>

        <Link
          href="/knowledge"
          className="text-xs font-mono font-bold text-indigo-400 hover:text-indigo-300 underline self-end sm:self-auto"
        >
          MANAGE KNOWLEDGE BASES &rarr;
        </Link>
      </div>

      {/* Upload card container */}
      <div className="rounded-xl border border-zinc-900 bg-zinc-950/20 p-5 shadow-inner">
        <div className="flex items-center gap-2 text-indigo-400 mb-4 select-none">
          <FolderPlus className="h-4.5 w-4.5" />
          <h3 className="text-xs font-extrabold uppercase font-mono tracking-wider text-zinc-350">
            Ingest Document Assets
          </h3>
        </div>
        <DocumentUpload kbName={selectedKb} onUploadStart={handleUploadStart} />
      </div>

      {/* Active uploads timelines */}
      {activeUploads.length > 0 && (
        <div className="space-y-3.5 animate-slide-in select-none">
          <span className="text-[10px] uppercase font-extrabold font-mono text-zinc-500 tracking-wider block">
            Ingestion Pipeline Active
          </span>
          <div className="space-y-2">
            {activeUploads.map((u) => (
              <div
                key={u.taskId}
                className="flex items-center gap-3 rounded-xl border border-zinc-900 bg-zinc-950 p-4 shadow-inner"
              >
                <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-zinc-250 truncate">{u.fileName}</p>
                  <p className="text-[8px] font-mono text-zinc-400 uppercase mt-0.5">Task ID: {u.taskId.substring(0, 16)}</p>
                </div>
                {u.task && (
                  <Badge variant="yellow" className="text-[9px] font-mono font-bold uppercase">{u.task.status}</Badge>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ingested Documents List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between border-b border-zinc-900 pb-2 select-none">
          <span className="text-[10px] uppercase font-extrabold font-mono text-zinc-400 tracking-wider">
            Ingested Assets List ({documents.length} files)
          </span>
          <span className="flex items-center gap-1 font-mono text-[9px] text-zinc-500 uppercase">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" /> local sandbox
          </span>
        </div>

        {loadingDocs ? (
          <div className="rounded-xl border border-dashed border-zinc-900 p-12 text-center text-xs text-zinc-600 font-mono select-none">
            <Loader2 className="h-6 w-6 animate-spin text-indigo-400 mx-auto mb-3" />
            <span>Loading library document index...</span>
          </div>
        ) : (
          <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-4 shadow-inner select-text">
            <DocumentList documents={documents} />
          </div>
        )}
      </div>

    </div>
  );
}
