"use client";

import { useState, useRef, type DragEvent, type FormEvent } from "react";
import { useUploadPolling } from "@/lib/use-upload-polling";
import { Upload, FileText, X } from "lucide-react";
import { uploadDocument, pollUploadTask } from "@/lib/knowledge";

interface DocumentUploadProps {
  kbName: string;
  onUploadStart: (taskId: string, fileName: string) => void;
}

export function DocumentUpload({ kbName, onUploadStart }: DocumentUploadProps) {
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useUploadPolling<typeof pollUploadTask>(activeTaskId, {
    fetcher: pollUploadTask,
    intervalMs: 2000,
    maxAttempts: 60,
    onComplete: () => {
      setUploading(null);
      setSelectedFile(null);
      setActiveTaskId(null);
    },
    onFailed: () => {
      setUploading(null);
      setActiveTaskId(null);
    },
    onError: () => {
      setUploading(null);
      setActiveTaskId(null);
    },
  });

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) setSelectedFile(file);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) setSelectedFile(file);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !kbName || uploading) return;
    setUploading(selectedFile.name);
    const result = await uploadDocument(selectedFile, kbName);
    if (result && result.task_id) {
      onUploadStart(result.task_id, selectedFile.name);
      setActiveTaskId(result.task_id);
    } else {
      setUploading(null);
    }
  };

  const ext = selectedFile?.name.split(".").pop()?.toLowerCase();
  const allowed = ["pdf", "txt", "md"];
  const valid = selectedFile ? allowed.includes(ext ?? "") : false;

  return (
    <form
      onSubmit={handleSubmit}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
        dragging
          ? "border-indigo-500 bg-indigo-500/5"
          : "border-zinc-700 bg-zinc-900/30"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.md"
        onChange={handleFileSelect}
        aria-label="Upload document file"
        className="hidden"
      />

      {!selectedFile ? (
        <div
          onClick={() => inputRef.current?.click()}
          className="cursor-pointer space-y-2"
        >
          <Upload className="mx-auto h-8 w-8 text-zinc-600" />
          <p className="text-sm text-zinc-400">
            Drop a file here, or{" "}
            <span className="text-indigo-400 underline">browse</span>
          </p>
          <p className="text-xs text-zinc-600">PDF, TXT, MD</p>
        </div>
      ) : (
        <div className="flex items-center justify-center gap-3">
          <FileText className="h-5 w-5 text-zinc-500" />
          <div className="text-left">
            <p className="text-sm text-zinc-300">{selectedFile.name}</p>
            <p className="text-xs text-zinc-600">
              {(selectedFile.size / 1024).toFixed(1)} KB
              {!valid && " · Unsupported format"}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setSelectedFile(null)}
            aria-label="Remove selected file"
            className="rounded p-1 text-zinc-600 hover:bg-zinc-800 hover:text-zinc-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {selectedFile && valid && (
        <button
          type="submit"
          disabled={!kbName || !!uploading}
          aria-label="Upload to knowledge base"
          className="mt-4 rounded bg-zinc-100 px-4 py-1.5 text-xs font-semibold text-zinc-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {uploading ? "Uploading..." : "Upload to KB"}
        </button>
      )}
    </form>
  );
}
