"use client";

import { useState, useEffect, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { DocumentUpload } from "@/components/documents/document-upload";
import { DocumentList } from "@/components/documents/document-list";
import { fetchKnowledgeBases, type UploadTask } from "@/lib/knowledge";

type ActiveUpload = {
  taskId: string;
  fileName: string;
  task: UploadTask | null;
};

export default function DocumentsPage() {
  const [kbNames, setKbNames] = useState<string[]>([]);
  const [selectedKb, setSelectedKb] = useState("");
  const [activeUploads, setActiveUploads] = useState<ActiveUpload[]>([]);

  // Load available KB names
  const loadKbs = useCallback(async () => {
    const bases = await fetchKnowledgeBases();
    if (bases) {
      setKbNames(bases.map((b) => b.name));
      if (bases.length > 0 && !selectedKb) {
        setSelectedKb(bases[0].name);
      }
    }
  }, [selectedKb]);

  useEffect(() => {
    loadKbs();
  }, [loadKbs]);

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
    }, 3000);
    return () => clearInterval(interval);
  }, [activeUploads.length]);

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <p className="text-sm text-zinc-500">
          Upload PDF, TXT, or MD files to build a knowledge base with PageIndex
          tree and optional vector embeddings.
        </p>
      </div>

      {/* KB selector */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-zinc-500">Target KB:</label>
        <select
          value={selectedKb}
          onChange={(e) => setSelectedKb(e.target.value)}
          className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-zinc-600"
        >
          {kbNames.length === 0 ? (
            <option value="">No KBs — upload creates one</option>
          ) : (
            kbNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))
          )}
        </select>
        <a
          href="/knowledge"
          className="text-xs text-indigo-400 underline hover:text-indigo-300"
        >
          Manage KBs →
        </a>
      </div>

      {/* Upload zone */}
      <DocumentUpload kbName={selectedKb} onUploadStart={handleUploadStart} />

      {/* Active uploads */}
      {activeUploads.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
            Processing
          </p>
          {activeUploads.map((u) => (
            <div
              key={u.taskId}
              className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-2"
            >
              <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
              <span className="text-sm text-zinc-300">{u.fileName}</span>
              {u.task && (
                <Badge variant="yellow">{u.task.status}</Badge>
              )}
              <span className="ml-auto text-xs text-zinc-600 font-mono">
                {u.taskId.slice(0, 8)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Document list — placeholder until backend is running */}
      <DocumentList documents={[]} />
    </div>
  );
}
