"use client";

import { useRef, type RefObject, type ChangeEvent, type DragEvent } from "react";
import { Upload, FileText, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { KbSelector } from "@/components/shared/kb-selector";

type DocumentInfo = {
  doc_id: string;
  page_count?: number;
  status: "indexed" | "processing" | "failed";
};

interface SourcesSidebarProps {
  documents: DocumentInfo[];
  loadingDocs: boolean;
  selectedDocId: string;
  onSelectDoc: (docId: string) => void;
  kbName: string;
  kbOptions: { value: string; label: string }[];
  onKbChange: (kb: string) => void;
  uploadProgress: string | null;
  dragging: boolean;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: DragEvent) => void;
  onFileChange: (e: ChangeEvent<HTMLInputElement>) => void;
  fileInputRef: RefObject<HTMLInputElement | null>;
  solveStatus: string;
  className?: string;
}

export function SourcesSidebar({
  documents,
  loadingDocs,
  selectedDocId,
  onSelectDoc,
  kbName,
  kbOptions,
  onKbChange,
  uploadProgress,
  dragging,
  onDragOver,
  onDragLeave,
  onDrop,
  onFileChange,
  fileInputRef,
  solveStatus,
  className = "",
}: SourcesSidebarProps) {
  const triggerFileBrowser = () => fileInputRef.current?.click();

  return (
    <aside className={`w-80 shrink-0 border-r border-border bg-card/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in ${className}`}>
      <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
        <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
          <span className="h-4 w-4 text-indigo-400" />
          Sources Scope
        </span>
        <Badge variant="zinc" className="text-[10px] text-zinc-500 border-zinc-800 font-mono">
          {documents.length} docs
        </Badge>
      </div>

      <div className="deep-scrollbar flex-1 overflow-y-auto p-4 space-y-5">
        <KbSelector
          kbOptions={kbOptions}
          selectedKb={kbName}
          onSelect={onKbChange}
        />

        <div className="space-y-2">
          <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
            Ingest Document
          </label>
          <input
            type="file"
            ref={fileInputRef}
            accept=".pdf,.txt,.md"
            onChange={onFileChange}
            aria-label="Upload document to knowledge base"
            className="hidden"
          />
          <button
            type="button"
            onDragOver={onDragOver}
            onDragLeave={() => onDragLeave()}
            onDrop={onDrop}
            onClick={triggerFileBrowser}
            className={`focus-ring pressable min-h-32 w-full rounded-xl border border-dashed p-4 text-center cursor-pointer flex flex-col items-center justify-center gap-2 ${
              dragging
                ? "border-indigo-500 bg-indigo-500/10"
                : "border-zinc-800 bg-zinc-950/20 hover:border-zinc-750 hover:bg-zinc-950/40"
            }`}
            aria-label="Choose or drop a document to upload"
          >
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
                  <p className="text-xs text-zinc-300 font-medium">Drag & Drop file</p>
                  <p className="text-[10px] text-zinc-500 mt-0.5">PDF, TXT or MD (Local)</p>
                </div>
              </>
            )}
          </button>
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
            <div className="deep-scrollbar space-y-1.5 min-h-24 max-h-[300px] overflow-y-auto pr-1">
              {documents.map((doc) => (
                <button
                  type="button"
                  key={doc.doc_id}
                  onClick={() => onSelectDoc(doc.doc_id)}
                  className={`focus-ring pressable flex min-h-11 w-full items-center justify-between rounded-lg border p-2.5 text-left cursor-pointer ${
                    doc.doc_id === selectedDocId
                      ? "bg-indigo-950/20 border-indigo-500/30 text-indigo-200"
                      : "border-zinc-900/60 bg-zinc-950/40 text-zinc-400 hover:bg-zinc-900/30"
                  }`}
                  aria-pressed={doc.doc_id === selectedDocId}
                  aria-label={`Select document ${doc.doc_id}`}
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <FileText className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className={`text-xs truncate font-medium ${doc.doc_id === selectedDocId ? "text-indigo-300" : "text-zinc-300"}`}>
                        {doc.doc_id}
                      </p>
                      {doc.page_count != null && (
                        <p className="text-[9px] text-zinc-600 font-mono">{doc.page_count} pages</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        doc.status === "indexed"
                          ? "bg-success"
                          : doc.status === "processing"
                            ? "animate-pulse bg-warning"
                            : "bg-danger"
                      }`}
                    />
                    <span className="text-[9px] font-mono text-zinc-600 capitalize">
                      {doc.status}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="p-4 border-t border-zinc-900 bg-zinc-950/40 text-[10px] text-zinc-500 font-mono flex items-center justify-between">
        <span>Diagnostics:</span>
        <Badge variant={solveStatus === "open" ? "green" : "zinc"}>
          {solveStatus}
        </Badge>
      </div>
    </aside>
  );
}
