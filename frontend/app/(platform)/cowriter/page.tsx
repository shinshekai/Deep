"use client";

import { useState, useEffect } from "react";
import {
  PenTool, Minimize2, Maximize2, Quote, Loader2, Sparkles, Clipboard,
  Trash2, Library, AlertCircle, X, Check, PanelLeft, PanelRight, Database
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { API_BASE_URL, secureFetch } from "@/lib/config";

type ProvenanceSource = {
  doc_id: string;
  page: number | string;
  relevance_score: number;
  snippet: string;
};

type Provenance = {
  action: string;
  model: string;
  timestamp: number;
  kb_name?: string;
  retrieval_pipeline?: string;
  sources?: ProvenanceSource[];
};

export default function CoWriterPage() {
  const [text, setText] = useState("");
  const [instruction, setInstruction] = useState("");
  const [selectedKb, setSelectedKb] = useState("default");
  const [pipeline, setPipeline] = useState("combined");
  const [activeModel, setActiveModel] = useState("Qwen3-1.7B-Q4_K_M");
  const [kbs, setKbs] = useState<{ name: string }[]>([]);
  const [models, setModels] = useState<Record<string, unknown>[]>([]);

  // Action status
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Provenance logs from edits/annotations
  const [provenanceHistory, setProvenanceHistory] = useState<Provenance[]>([]);

  // Layout states
  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightSidebar, setShowRightSidebar] = useState(true);

  useEffect(() => {
    loadKbs();
    loadModels();
  }, []);

  const loadKbs = async () => {
    try {
      const res = await secureFetch(`${API_BASE_URL}/knowledge/bases`);
      if (res.ok) {
        const data = await res.json();
        setKbs(data);
        if (data.length > 0) {
          setSelectedKb(data[0].name);
        }
      }
    } catch {}
  };

  const loadModels = async () => {
    try {
      const res = await secureFetch(`${API_BASE_URL}/models`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setModels(data);
        }
      }
    } catch {}
  };

  const handleEdit = async (action: "shorten" | "expand" | "rewrite") => {
    if (!text.trim()) {
      setError("Please enter some text in the editor first.");
      return;
    }
    if (action === "rewrite" && !instruction.trim()) {
      setError("Please provide custom instructions for the rewrite.");
      return;
    }

    setIsProcessing(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await secureFetch(`${API_BASE_URL}/cowriter/edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          action,
          instruction: action === "rewrite" ? instruction : undefined,
          model_id: activeModel,
        }),
      });

      if (!res.ok) throw new Error(`Failed to process action: ${action}`);
      const data = await res.json();

      setText(data.text);
      setSuccessMsg(`Successfully applied AI ${action}!`);
      
      if (data.provenance) {
        setProvenanceHistory((prev) => [data.provenance, ...prev]);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to process text edit");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAnnotate = async () => {
    if (!text.trim()) {
      setError("Please enter some text in the editor first.");
      return;
    }

    setIsProcessing(true);
    setError(null);
    setSuccessMsg(null);

    try {
      const res = await secureFetch(`${API_BASE_URL}/cowriter/annotate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          kb_name: selectedKb,
          retrieval_pipeline: pipeline,
          model_id: activeModel,
        }),
      });

      if (!res.ok) throw new Error("Failed to auto-annotate document");
      const data = await res.json();

      setText(data.text);
      setSuccessMsg("Auto-annotations and reference list successfully generated!");

      if (data.provenance) {
        setProvenanceHistory((prev) => [data.provenance, ...prev]);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to annotate document");
    } finally {
      setIsProcessing(false);
    }
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(text);
    setSuccessMsg("Copied editor text to clipboard!");
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const wordCount = text.trim() === "" ? 0 : text.trim().split(/\s+/).length;
  const charCount = text.length;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-3 sm:-mx-5 md:-mx-6 lg:-mx-8 -my-3 sm:-my-5 md:-my-6 lg:-my-8 overflow-hidden bg-zinc-950 text-zinc-100 antialiased relative">
      
      {/* ─── LEFT COLUMN: AI Configuration Toolbar ─── */}
      {showLeftSidebar && (
        <aside className="w-80 shrink-0 border-r border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-indigo-400" />
              AI Studio Rails
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {/* Model Target Selection */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Target Inference Model
              </label>
              <select
                value={activeModel}
                onChange={(e) => setActiveModel(e.target.value)}
                disabled={isProcessing}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans disabled:opacity-50"
              >
                {models.length === 0 ? (
                  <>
                    <option value="Qwen3-1.7B-Q4_K_M">Qwen3-1.7B (Q4_K_M)</option>
                    <option value="Qwen3-8B">Qwen3-8B</option>
                  </>
                ) : (
                  models.map((m) => (
                    <option key={String(m.id)} value={String(m.id)}>
                      {String(m.name || m.id)} ({String(m.tier)})
                    </option>
                  ))
                )}
              </select>
            </div>

            {/* Quick editing helpers */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Quick Actions
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => handleEdit("shorten")}
                  disabled={isProcessing || !text.trim()}
                  className="flex items-center justify-center gap-1.5 rounded-lg border border-zinc-900 bg-zinc-950/40 text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300 px-3 py-2 text-xs font-semibold transition select-none cursor-pointer disabled:opacity-40"
                >
                  <Minimize2 className="h-3.5 w-3.5 text-zinc-500" />
                  Shorten
                </button>
                <button
                  onClick={() => handleEdit("expand")}
                  disabled={isProcessing || !text.trim()}
                  className="flex items-center justify-center gap-1.5 rounded-lg border border-zinc-900 bg-zinc-950/40 text-zinc-500 hover:bg-zinc-900 hover:text-zinc-300 px-3 py-2 text-xs font-semibold transition select-none cursor-pointer disabled:opacity-40"
                >
                  <Maximize2 className="h-3.5 w-3.5 text-zinc-500" />
                  Expand
                </button>
              </div>
            </div>

            {/* Custom instruction rewrite */}
            <div className="space-y-3.5 border-t border-zinc-900/60 pt-4">
              <div className="space-y-2">
                <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                  Custom Rewrite Prompt
                </label>
                <input
                  type="text"
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  disabled={isProcessing}
                  placeholder="e.g. Rewrite in formal scientific prose..."
                  className="w-full rounded-lg border border-zinc-850 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans"
                />
              </div>
              <button
                onClick={() => handleEdit("rewrite")}
                disabled={isProcessing || !text.trim() || !instruction.trim()}
                className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white hover:bg-indigo-500 transition select-none cursor-pointer disabled:opacity-40"
              >
                {isProcessing && instruction ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PenTool className="h-3.5 w-3.5" />}
                Apply Rewrite
              </button>
            </div>

            {/* Auto Annotate citations */}
            <div className="space-y-3.5 border-t border-zinc-900/60 pt-4">
              <div className="space-y-3.5">
                <div className="space-y-1.5">
                  <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">Target Knowledge Base</label>
                  <select
                    value={selectedKb}
                    onChange={(e) => setSelectedKb(e.target.value)}
                    disabled={isProcessing}
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 focus:outline-none"
                  >
                    {kbs.length === 0 ? (
                      <option value="default">default</option>
                    ) : (
                      kbs.map((kb) => (
                        <option key={kb.name} value={kb.name}>{kb.name}</option>
                      ))
                    )}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">Search Pipeline</label>
                  <select
                    value={pipeline}
                    onChange={(e) => setPipeline(e.target.value)}
                    disabled={isProcessing}
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 focus:outline-none"
                  >
                    <option value="tree">PageIndex Tree</option>
                    <option value="hybrid">Hybrid RAG</option>
                    <option value="naive">Naive Vector</option>
                    <option value="combined">Combined Pipeline</option>
                  </select>
                </div>
              </div>

              <button
                onClick={handleAnnotate}
                disabled={isProcessing || !text.trim()}
                className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-500 transition select-none cursor-pointer disabled:opacity-40"
              >
                {isProcessing && !instruction ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Quote className="h-3.5 w-3.5" />}
                Auto-Annotate Draft
              </button>
            </div>
          </div>

          <div className="p-4 border-t border-zinc-900 bg-zinc-950/40 text-[10px] text-zinc-500 font-mono flex items-center justify-between">
            <span className="flex items-center gap-1 font-mono uppercase"><Database className="h-3.5 w-3.5 text-indigo-400" /> Grounded cite</span>
            <span className="text-[9px] uppercase font-bold bg-zinc-900 px-1 py-0.5 rounded text-zinc-400">CoWriter</span>
          </div>
        </aside>
      )}

      {/* ─── CENTER COLUMN: Drafting workspace ─── */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950 relative select-text">
        {/* Solve Control Toolbar */}
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-900 bg-zinc-950/40 px-4 select-none">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowLeftSidebar(!showLeftSidebar)}
              className={`p-1.5 rounded-lg border transition ${
                showLeftSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
              title="Toggle Controls Sidebar"
              aria-expanded={showLeftSidebar}
            >
              <PanelLeft className="h-4 w-4" />
            </button>
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <span className="text-xs font-semibold text-zinc-250 font-mono">Academic Draft Editor</span>
          </div>

          <div className="flex items-center gap-2">
            {text.trim() !== "" && (
              <div className="flex items-center gap-2">
                <button
                  onClick={copyToClipboard}
                  className="flex items-center gap-1 rounded bg-zinc-900 border border-zinc-850 hover:border-zinc-700 px-2 py-1 text-xs text-zinc-400 transition"
                  title="Copy Editor text"
                >
                  <Clipboard className="h-3.5 w-3.5" />
                  <span>Copy text</span>
                </button>
                <button
                  onClick={() => setText("")}
                  className="flex items-center gap-1 rounded bg-zinc-900 border border-zinc-850 hover:border-zinc-750 hover:text-red-400 px-2 py-1 text-xs text-zinc-500 transition"
                  title="Clear editor"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Clear</span>
                </button>
              </div>
            )}
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <button
              onClick={() => setShowRightSidebar(!showRightSidebar)}
              className={`p-1.5 rounded-lg border transition ${
                showRightSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
              title="Toggle Provenance Sidebar"
              aria-expanded={showRightSidebar}
            >
              <PanelRight className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Large main editor viewport */}
        <div className="flex-1 p-4 md:p-6 select-text bg-zinc-950 flex flex-col gap-3">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={isProcessing}
            placeholder="Type, outline, or paste raw materials to start. Use the configuration panel on the left to shorten, expand, or auto-annotate local citations..."
            className="flex-1 w-full rounded-xl border border-zinc-900 bg-zinc-950/20 p-4 text-xs md:text-sm text-zinc-100 placeholder-zinc-700 focus:outline-none focus:border-indigo-650 font-sans leading-relaxed resize-none overflow-y-auto select-text"
          />

          <div className="flex justify-between items-center text-[10px] font-mono text-zinc-400 px-1.5 select-none shrink-0 border-t border-zinc-900/60 pt-2">
            <span>WORDS: {wordCount}</span>
            <span>CHARACTERS: {charCount}</span>
          </div>
        </div>
      </main>

      {/* ─── RIGHT COLUMN: Citation Provenance ─── */}
      {showRightSidebar && (
        <aside className="w-80 shrink-0 border-l border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <Library className="h-4 w-4 text-indigo-400" />
              Provenance Logs
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 select-text">
            {provenanceHistory.length === 0 ? (
              <div className="text-center py-16 space-y-2 text-zinc-500 select-none">
                <Library className="h-6 w-6 text-zinc-700 mx-auto mb-1 animate-pulse" />
                <p className="text-xs font-bold uppercase tracking-wider font-mono">No edits logged</p>
                <p className="text-[10px] text-zinc-500 font-sans max-w-[180px] mx-auto leading-normal">
                  Citations and edit operations will log dynamic provenance references here in real-time.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {provenanceHistory.map((prov, idx) => (
                  <div 
                    key={idx} 
                    className="rounded-xl border border-zinc-900 bg-zinc-950 p-3.5 space-y-2.5 shadow-inner"
                  >
                    <div className="flex items-center justify-between text-[9px] font-mono border-b border-zinc-900 pb-1.5 select-none">
                      <Badge variant="zinc" className="uppercase text-[8px] font-mono bg-zinc-900 text-zinc-400">
                        {prov.action}
                      </Badge>
                      <span className="text-zinc-600">
                        {new Date(prov.timestamp * 1000).toLocaleTimeString()}
                      </span>
                    </div>

                    <div className="text-[9px] font-mono text-zinc-500 leading-normal space-y-0.5 select-none">
                      <div>Model: {prov.model}</div>
                      {prov.kb_name && <div>KB: {prov.kb_name}</div>}
                    </div>

                    {/* Cited sources list (NotebookLM citation visual style) */}
                    {prov.sources && prov.sources.length > 0 && (
                      <div className="space-y-2 border-t border-zinc-900/60 pt-2.5 mt-1.5">
                        <span className="text-[9px] uppercase font-bold text-zinc-400 font-mono tracking-wider block select-none">
                          Sources Grounded
                        </span>
                        <div className="space-y-1.5">
                          {prov.sources.map((src, sIndex) => (
                            <div 
                              key={sIndex} 
                              className="rounded-lg border border-zinc-900/80 bg-zinc-950/40 p-2 space-y-1"
                            >
                              <div className="flex items-center justify-between text-[9px] font-mono select-none">
                                <span className="text-indigo-400 font-semibold truncate max-w-[110px]" title={src.doc_id}>
                                  {src.doc_id.split("/").pop()}
                                </span>
                                <span className="text-zinc-600">p.{src.page}</span>
                              </div>
                              {src.snippet && (
                                <p className="text-[9px] text-zinc-500 leading-relaxed italic select-text pl-1 border-l border-zinc-900">
                                  &quot;{src.snippet}&quot;
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      )}

      {/* Processing loading spinner overlay */}
      {isProcessing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs select-none pointer-events-auto">
          <div className="rounded-xl border border-zinc-900 bg-zinc-950 p-6 flex flex-col items-center gap-2.5 shadow-2xl">
            <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
            <p className="text-[10px] uppercase font-bold font-mono tracking-wider text-zinc-400">
              CoWriter is compiling edit...
            </p>
          </div>
        </div>
      )}

      {/* Global alert toast banners */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 select-none pointer-events-none max-w-sm" role="status" aria-live="polite">
        {successMsg && (
          <div className="rounded-lg border border-emerald-900 bg-emerald-950/80 backdrop-blur-md px-4 py-3 text-xs text-emerald-400 flex items-center gap-2 pointer-events-auto shadow-lg shadow-emerald-950/20">
            <Check className="h-4 w-4 text-emerald-400 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}
        {error && (
          <div className="rounded-lg border border-red-900 bg-red-950/80 backdrop-blur-md px-4 py-3 text-xs text-red-400 flex items-center gap-2 pointer-events-auto shadow-lg shadow-red-950/20">
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
            <span className="select-text">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-400 pointer-events-auto" aria-label="Dismiss error">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

    </div>
  );
}
