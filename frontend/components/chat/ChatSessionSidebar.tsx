"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Database, Upload, Loader2, FileText } from "lucide-react";
import { KbSelector } from "@/components/shared/kb-selector";
import { useUploadPolling } from "@/lib/use-upload-polling";
import {
  uploadDocument,
  pollUploadTask,
  fetchKnowledgeBases,
  type KnowledgeBase,
} from "@/lib/knowledge";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import { Badge } from "@/components/ui/badge";

type DocumentInfo = {
  doc_id: string;
  page_count?: number;
  status: "indexed" | "processing" | "failed";
};

interface ChatSessionSidebarProps {
  onKbChange: (kb: string) => void;
}

export function ChatSessionSidebar({
  onKbChange,
}: ChatSessionSidebarProps) {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selectedKb, setSelectedKb] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [activeUploadTaskId, setActiveUploadTaskId] = useState<string | null>(
    null
  );
  const [pendingUploadName, setPendingUploadName] = useState<string | null>(
    null
  );
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadKbs = async () => {
    try {
      const bases = await fetchKnowledgeBases();
      if (bases && bases.length > 0) {
        setKbs(bases);
        if (!selectedKb) {
          const first = bases[0].name;
          setSelectedKb(first);
          onKbChange(first);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const loadDocuments = useCallback(async (kbName: string) => {
    if (!kbName) {
      setDocuments([]);
      return;
    }
    setLoadingDocs(true);
    try {
      const res = await secureFetch(
        `${API_BASE_URL}/knowledge/${encodeURIComponent(kbName)}/documents`
      );
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setDocuments(data);
        } else if (data.documents && Array.isArray(data.documents)) {
          setDocuments(data.documents);
        } else {
          setDocuments([]);
        }
      }
    } catch {
      setDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  }, []);

  useEffect(() => {
    loadKbs();
  }, []);

  useEffect(() => {
    loadDocuments(selectedKb);
  }, [selectedKb, loadDocuments]);

  useUploadPolling<typeof pollUploadTask>(activeUploadTaskId, {
    fetcher: pollUploadTask,
    intervalMs: 2000,
    maxAttempts: 60,
    onComplete: () => {
      setUploadProgress(null);
      setActiveUploadTaskId(null);
      setPendingUploadName(null);
      if (selectedKb) loadDocuments(selectedKb);
    },
    onFailed: (task) => {
      const name = pendingUploadName ?? "document";
      setUploadProgress(null);
      setActiveUploadTaskId(null);
      setPendingUploadName(null);
      toast.error(
        `Document parsing failed: ${name} (${task?.message ?? "unknown error"})`
      );
    },
    onError: () => {
      setUploadProgress(null);
      setActiveUploadTaskId(null);
      setPendingUploadName(null);
    },
  });

  const processFileUpload = async (file: File) => {
    const ext = file.name.split(".").pop()?.toLowerCase();
    const allowed = ["pdf", "txt", "md"];
    if (!allowed.includes(ext ?? "")) {
      toast.error("Supported document formats: PDF, TXT, MD");
      return;
    }
    setUploadProgress(file.name);
    const result = await uploadDocument(file, selectedKb);
    if (result && result.task_id) {
      setPendingUploadName(file.name);
      setActiveUploadTaskId(result.task_id);
    } else {
      setUploadProgress(null);
      toast.error("Failed to initiate file ingestion.");
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => setDragging(false);

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!selectedKb) {
      toast.error("Please select or create a Knowledge Base scope first.");
      return;
    }
    const file = e.dataTransfer.files[0];
    if (file) await processFileUpload(file);
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await processFileUpload(file);
  };

  const handleKbSelect = (kb: string) => {
    setSelectedKb(kb);
    onKbChange(kb);
  };

  return (
    <aside className="w-80 shrink-0 border-r border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
      <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
        <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
          <Database className="h-4 w-4 text-indigo-400" />
          Sources Scope
        </span>
        <Badge
          variant="zinc"
          className="text-[10px] text-zinc-500 border-zinc-800 font-mono"
        >
          {documents.length} docs
        </Badge>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        <KbSelector
          kbOptions={kbs.map((kb) => ({ value: kb.name, label: kb.name }))}
          selectedKb={selectedKb}
          onSelect={handleKbSelect}
        />

        <div className="space-y-2">
          <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
            Ingest Document
          </label>
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`rounded-xl border border-dashed p-4 text-center cursor-pointer transition flex flex-col items-center justify-center gap-2 ${
              dragging
                ? "border-indigo-500 bg-indigo-500/10"
                : "border-zinc-800 bg-zinc-950/20 hover:border-zinc-750 hover:bg-zinc-950/40"
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,.txt,.md"
              onChange={handleFileChange}
              className="hidden"
              aria-label="Upload document"
            />
            {uploadProgress ? (
              <div className="space-y-2 py-2">
                <Loader2 className="h-6 w-6 text-indigo-400 animate-spin mx-auto" />
                <p className="text-[10px] text-zinc-500 font-mono truncate max-w-[180px]">
                  Parsing {uploadProgress}...
                </p>
              </div>
            ) : (
              <>
                <Upload className="h-5 w-5 text-zinc-500" />
                <div>
                  <p className="text-xs text-zinc-300 font-medium">
                    Drag & Drop file
                  </p>
                  <p className="text-[10px] text-zinc-500 mt-0.5">
                    PDF, TXT or MD (Local)
                  </p>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
            Workspace Contents
          </label>
          {loadingDocs ? (
            <div className="flex items-center justify-center py-8 text-zinc-500 text-xs gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading library node...</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-lg border border-dashed border-zinc-900 p-6 text-center text-zinc-500 text-xs">
              No indexed resources in scope. Ingest files above.
            </div>
          ) : (
            <div className="space-y-1.5 max-h-[300px] overflow-y-auto pr-1">
              {documents.map((doc) => (
                <div
                  key={doc.doc_id}
                  className="flex items-center justify-between rounded-lg border border-zinc-900/60 bg-zinc-950/40 px-3 py-2"
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <FileText className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p
                        className="text-xs text-zinc-300 truncate font-medium"
                        title={doc.doc_id}
                      >
                        {doc.doc_id}
                      </p>
                      {doc.page_count != null && (
                        <p className="text-[9px] text-zinc-600 font-mono">
                          {doc.page_count} pages
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        doc.status === "indexed"
                          ? "bg-emerald-500 shadow-emerald-500/20"
                          : doc.status === "processing"
                            ? "animate-pulse bg-amber-500"
                            : "bg-red-500"
                      }`}
                    />
                    <span className="text-[9px] font-mono text-zinc-600 capitalize">
                      {doc.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="p-4 border-t border-zinc-900 bg-zinc-950/40 text-[10px] text-zinc-600 font-mono">
        Provider: Local Offline Cascade
      </div>
    </aside>
  );
}
