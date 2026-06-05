"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useUploadPolling } from "@/lib/use-upload-polling";
import { useWebSocket } from "@/providers/websocket-provider";
import { Badge } from "@/components/ui/badge";
import type {
  SolveQuery,
  AgentStepFrame,
  Citation,
  CompleteFrame,
  ErrorFrame,
  IndexNode
} from "@/types/api";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import { 
  PlusCircle, FileText, CheckCircle2, ChevronRight, ChevronDown, 
  Sparkles, Database, Plus, Trash, Copy, BookOpen, Layers, 
  ArrowRightLeft, AlertCircle, RefreshCw, X, Lightbulb, BookMarked, Save,
  Upload, PanelLeft, PanelRight, Shield, Zap, Search, Clock, Cpu, Loader2
} from "lucide-react";
import { uploadDocument, pollUploadTask, fetchKnowledgeBases, type KnowledgeBase } from "@/lib/knowledge";

// Agent metadata for pipeline render
const agentMeta: Record<
  string,
  { icon: any; label: string; color: string; bg: string; border: string }
> = {
  investigate: { 
    icon: Search, 
    label: "Investigate Agent", 
    color: "text-indigo-400", 
    bg: "bg-indigo-950/10",
    border: "border-indigo-900/30" 
  },
  note: { 
    icon: FileText, 
    label: "Annotator Agent", 
    color: "text-blue-400", 
    bg: "bg-blue-950/10",
    border: "border-blue-900/30" 
  },
  plan: { 
    icon: Layers, 
    label: "Planner Agent", 
    color: "text-amber-400", 
    bg: "bg-amber-950/10",
    border: "border-amber-900/30" 
  },
  manager: { 
    icon: Cpu, 
    label: "Mission Controller", 
    color: "text-purple-400", 
    bg: "bg-purple-950/10",
    border: "border-purple-900/30" 
  },
  solve: { 
    icon: Sparkles, 
    label: "Solve Agent", 
    color: "text-emerald-400", 
    bg: "bg-emerald-950/10",
    border: "border-emerald-900/30" 
  },
  check: { 
    icon: CheckCircle2, 
    label: "Checker Agent", 
    color: "text-cyan-400", 
    bg: "bg-cyan-950/10",
    border: "border-cyan-900/30" 
  },
  format: { 
    icon: Layers, 
    label: "Formatter Agent", 
    color: "text-zinc-400", 
    bg: "bg-zinc-900/20",
    border: "border-zinc-800" 
  },
};

type SolveState = "idle" | "streaming" | "complete" | "error";

type DocumentInfo = {
  doc_id: string;
  page_count?: number;
  status: "indexed" | "processing" | "failed";
};

// Render recursive tree node component for PageIndex
function TreeItem({ node, depth = 0 }: { node: IndexNode; depth: number }) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="space-y-1 select-none">
      <div 
        onClick={() => setExpanded(!expanded)}
        className={`flex items-start gap-1.5 py-1 px-2 rounded-lg text-xs transition cursor-pointer hover:bg-zinc-900/40 ${
          expanded ? "bg-zinc-900/20 text-zinc-200" : "text-zinc-450 hover:text-zinc-300"
        }`}
        style={{ paddingLeft: `${depth * 10 + 8}px` }}
        role="button"
        aria-expanded={expanded}
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(!expanded); } }}
      >
        {hasChildren ? (
          <span className="mt-0.5 shrink-0">
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </span>
        ) : (
          <span className="h-3.5 w-3.5 mt-0.5 shrink-0 flex items-center justify-center">
            <span className="h-1 w-1 rounded-full bg-zinc-700" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium truncate">{node.title || "Untitled Heading"}</span>
            {node.start_index !== undefined && (
              <span className="text-[9px] font-mono text-zinc-500 font-bold shrink-0">
                p.{node.start_index}
              </span>
            )}
          </div>
          {expanded && node.summary && (
            <p className="mt-1 text-[10px] text-zinc-500 font-sans leading-relaxed whitespace-pre-wrap select-text border-l border-zinc-800 pl-2">
              {node.summary}
            </p>
          )}
        </div>
      </div>
      {expanded && hasChildren && (
        <div className="space-y-0.5">
          {node.children.map((child, i) => (
            <TreeItem key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SolvePage() {
  const { solveStatus, send, subscribe } = useWebSocket();
  const [state, setState] = useState<SolveState>("idle");
  
  // Custom Sidebar toggle
  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightSidebar, setShowRightSidebar] = useState(true);

  // Aggregated Pipeline Steps
  const [steps, setSteps] = useState<AgentStepFrame[]>([]);
  const [expandedStepIndex, setExpandedStepIndex] = useState<number | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [answer, setAnswer] = useState<CompleteFrame | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Input states
  const [text, setText] = useState("");
  const [kbName, setKbName] = useState("");
  const [mode, setMode] = useState<SolveQuery["mode"]>("auto");
  const [retrieval, setRetrieval] = useState<SolveQuery["retrieval_pipeline"]>("tree");
  const [kbOptions, setKbOptions] = useState<{ value: string; label: string }[]>([
    { value: "", label: "(none)" }
  ]);

  // Sources Lists (Left Panel)
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [activeUploadTaskId, setActiveUploadTaskId] = useState<string | null>(null);
  const [pendingUploadName, setPendingUploadName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  // Polling for upload status — uses the shared hook so the interval
  // is cleared on unmount and bounded by maxAttempts. The previous
  // inline setInterval leaked when the user navigated away.
  useUploadPolling<typeof pollUploadTask>(activeUploadTaskId, {
    fetcher: pollUploadTask,
    intervalMs: 2000,
    maxAttempts: 60,
    onComplete: () => {
      setUploadProgress(null);
      setActiveUploadTaskId(null);
      setPendingUploadName(null);
      if (kbName) loadDocuments(kbName);
    },
    onFailed: () => {
      const name = pendingUploadName ?? "document";
      setUploadProgress(null);
      setActiveUploadTaskId(null);
      setPendingUploadName(null);
      setErrorMsg(`Document parsing failed: ${name}`);
    },
    onError: () => {
      setUploadProgress(null);
      setActiveUploadTaskId(null);
      setPendingUploadName(null);
    },
  });

  // PageIndex Tree (Right Panel)
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [indexTree, setIndexTree] = useState<IndexNode | null>(null);
  const [loadingTree, setLoadingTree] = useState(false);
  const [treeSearch, setTreeSearch] = useState("");

  const sessionIdRef = useRef<string>(crypto.randomUUID());

  // Load KBs list on mount
  useEffect(() => {
    loadKbs();
  }, []);

  const loadKbs = async () => {
    try {
      const bases = await fetchKnowledgeBases();
      if (bases) {
        const mapped = bases.map((kb: any) => {
          const name = typeof kb === "string" ? kb : (kb.name || "default");
          return { value: name, label: name };
        });
        setKbOptions([{ value: "", label: "(none)" }, ...mapped]);
        if (mapped.length > 0 && !kbName) {
          setKbName(mapped[0].value);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Load documents inside selected KB
  const loadDocuments = useCallback(async (kb: string) => {
    if (!kb) {
      setDocuments([]);
      setSelectedDocId("");
      setIndexTree(null);
      return;
    }
    setLoadingDocs(true);
    try {
      const res = await secureFetch(`${API_BASE_URL}/knowledge/${encodeURIComponent(kb)}/documents`);
      if (res.ok) {
        const data = await res.json();
        const list = Array.isArray(data) ? data : (data.documents || []);
        setDocuments(list);
        if (list.length > 0 && !selectedDocId) {
          setSelectedDocId(list[0].doc_id);
        }
      }
    } catch {
      setDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  }, [selectedDocId]);

  useEffect(() => {
    loadDocuments(kbName);
  }, [kbName, loadDocuments]);

  // Load PageIndex tree
  const loadPageIndexTree = useCallback(async (kb: string, docId: string) => {
    if (!kb || !docId) {
      setIndexTree(null);
      return;
    }
    setLoadingTree(true);
    setIndexTree(null);
    try {
      const res = await secureFetch(
        `${API_BASE_URL}/knowledge/bases/${encodeURIComponent(kb)}/pageindex/${encodeURIComponent(docId)}`
      );
      if (res.ok) {
        const data = await res.json();
        setIndexTree(data.tree || data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingTree(false);
    }
  }, []);

  useEffect(() => {
    loadPageIndexTree(kbName, selectedDocId);
  }, [kbName, selectedDocId, loadPageIndexTree]);

  // Subscribe to agent steps (with delta streaming aggregation)
  useEffect(() => {
    return subscribe("agent_step", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      
      const agent = data.agent as string;
      const delta = (data.delta as string) || (data.content as string) || "";
      const timestamp = (data.timestamp as number) || (Date.now() / 1000);

      setSteps((prev) => {
        const existingIdx = prev.findIndex((s) => s.agent === agent);
        if (existingIdx !== -1) {
          const updated = [...prev];
          updated[existingIdx] = {
            ...updated[existingIdx],
            content: updated[existingIdx].content + delta,
            timestamp: timestamp,
          };
          return updated;
        } else {
          return [
            ...prev,
            {
              type: "agent_step",
              agent: agent as any,
              content: delta,
              timestamp: timestamp,
            },
          ];
        }
      });
    });
  }, [subscribe]);

  // Subscribe to citations
  useEffect(() => {
    return subscribe("citation", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      if (data.citation) {
        setCitations((prev) => [...prev, data.citation as Citation]);
      }
    });
  }, [subscribe]);

  // Subscribe to completion
  useEffect(() => {
    return subscribe("complete", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      setAnswer(data as CompleteFrame);
      setState("complete");
    });
  }, [subscribe]);

  // Subscribe to errors
  useEffect(() => {
    return subscribe("error", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      setErrorMsg((data as ErrorFrame).message ?? "Pipeline failure");
      setState("error");
    });
  }, [subscribe]);

  const handleSend = () => {
    if (!text.trim() || state === "streaming") return;
    setSteps([]);
    setCitations([]);
    setAnswer(null);
    setErrorMsg(null);
    sessionIdRef.current = crypto.randomUUID();
    setState("streaming");
    send({
      query: text.trim(),
      kb_name: kbName,
      mode,
      retrieval_pipeline: retrieval,
      session_id: sessionIdRef.current
    });
  };

  const copyToClipboard = (txt: string) => {
    navigator.clipboard.writeText(txt);
    setSuccessMsg("Copied reply to clipboard.");
    setTimeout(() => setSuccessMsg(null), 2500);
  };

  // Upload actions (Drag & Drop)
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => {
    setDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!kbName) {
      setErrorMsg("Select a Knowledge Base target first.");
      return;
    }
    const file = e.dataTransfer.files[0];
    if (file) {
      await processFileUpload(file);
    }
  };

  const triggerFileBrowser = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await processFileUpload(file);
    }
  };

  const processFileUpload = async (file: File) => {
    const ext = file.name.split(".").pop()?.toLowerCase();
    const allowed = ["pdf", "txt", "md"];
    if (!allowed.includes(ext ?? "")) {
      setErrorMsg("Supported formats: PDF, TXT, MD");
      return;
    }

    setUploadProgress(file.name);
    setErrorMsg(null);

    const result = await uploadDocument(file, kbName);
    if (result && result.task_id) {
      setPendingUploadName(file.name);
      setActiveUploadTaskId(result.task_id);
    } else {
      setUploadProgress(null);
      setErrorMsg("Failed to upload document.");
    }
  };

  // Filter tree nodes recursively based on search query
  const filterTree = (node: IndexNode | null, query: string): IndexNode | null => {
    if (!node) return null;
    if (!query) return node;

    const matchesThis = node.title.toLowerCase().includes(query.toLowerCase()) || 
                        node.summary.toLowerCase().includes(query.toLowerCase());

    const filteredChildren = node.children
      .map((child) => filterTree(child, query))
      .filter((child): child is IndexNode => child !== null);

    if (matchesThis || filteredChildren.length > 0) {
      return {
        ...node,
        children: filteredChildren,
      };
    }
    return null;
  };

  const filteredTree = filterTree(indexTree, treeSearch);

  // Suggested prompt list
  const suggestedPrompts = [
    "Identify any conflicting claims in these papers.",
    "Draft a step-by-step summary of the experimental results.",
    "Explain the theoretical formula derivation details."
  ];

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-3 sm:-mx-5 md:-mx-6 lg:-mx-8 -my-3 sm:-my-5 md:-my-6 lg:-my-8 overflow-hidden bg-zinc-950 text-zinc-100 antialiased relative">
      
      {/* ─── LEFT COLUMN: Sources & Context Scope ─── */}
      {showLeftSidebar && (
        <aside className="w-80 shrink-0 border-r border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <Database className="h-4 w-4 text-indigo-400" />
              Sources Scope
            </span>
            <Badge variant="zinc" className="text-[10px] text-zinc-500 border-zinc-800 font-mono">
              {documents.length} docs
            </Badge>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {/* KB Selection */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Active Knowledge Base
              </label>
              <select
                value={kbName}
                onChange={(e) => setKbName(e.target.value)}
                aria-label="Select active knowledge base"
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 focus:outline-none"
              >
                {kbOptions.map((o) => (
                  <option key={o.value} value={o.value}>{o.label || "(none)"}</option>
                ))}
              </select>
            </div>

            {/* Drag & Drop file ingestion */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Ingest Document
              </label>
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={triggerFileBrowser}
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
                  aria-label="Upload document to knowledge base"
                  className="hidden" 
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
                      <p className="text-xs text-zinc-300 font-medium">Drag & Drop file</p>
                      <p className="text-[10px] text-zinc-500 mt-0.5">PDF, TXT or MD (Local)</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Ingested Document files list */}
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
                      onClick={() => setSelectedDocId(doc.doc_id)}
                      className={`flex items-center justify-between rounded-lg border p-2.5 transition text-left cursor-pointer ${
                        doc.doc_id === selectedDocId
                          ? "bg-indigo-950/20 border-indigo-500/30 text-indigo-200"
                          : "border-zinc-900/60 bg-zinc-950/40 text-zinc-400 hover:bg-zinc-900/30"
                      }`}
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
                              ? "bg-emerald-500"
                              : doc.status === "processing"
                                ? "animate-pulse bg-amber-500"
                                : "bg-red-500"
                          }`}
                        />
                      </div>
                    </div>
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
      )}

      {/* ─── CENTER COLUMN: Smart Solve Interactive Workspace ─── */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950 relative select-text">
        {/* Solve Control Toolbar */}
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-900 bg-zinc-950/40 px-4 select-none">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowLeftSidebar(!showLeftSidebar)}
              className={`p-1.5 rounded-lg border transition ${
                showLeftSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
              aria-label="Toggle sources sidebar"
              aria-expanded={showLeftSidebar}
            >
              <PanelLeft className="h-4 w-4" />
            </button>
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <span className="text-xs font-semibold text-zinc-250 font-mono">Smart Solve Mission Ingest</span>
          </div>

          <div className="flex items-center gap-2">
            {state !== "idle" && (
              <button
                onClick={() => {
                  setState("idle");
                  setSteps([]);
                  setAnswer(null);
                  setCitations([]);
                }}
                className="flex items-center gap-1 rounded bg-zinc-900 hover:bg-zinc-800/80 px-2 py-1 text-xs text-zinc-400 transition"
                aria-label="Reset solve session"
              >
                Reset Solve
              </button>
            )}
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <button
              onClick={() => setShowRightSidebar(!showRightSidebar)}
              className={`p-1.5 rounded-lg border transition ${
                showRightSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
              aria-label="Toggle index tree sidebar"
              aria-expanded={showRightSidebar}
            >
              <PanelRight className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Primary workspace layout */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          <div className="max-w-3xl mx-auto space-y-6">
            
            {/* VRAM / Complexity telemetry info banner */}
            {state === "idle" && (
              <div className="rounded-xl border border-zinc-900/60 bg-zinc-950 p-5 space-y-4 select-none">
                <div className="flex items-center gap-2 text-indigo-400">
                  <Sparkles className="h-5 w-5 animate-pulse" />
                  <h2 className="text-sm font-bold text-zinc-200 uppercase tracking-wider font-mono">
                    Multi-Agent Synthesis Engine
                  </h2>
                </div>
                <p className="text-xs text-zinc-500 leading-relaxed font-sans">
                  Smart Solve executes a dual-loop deliberate agentic reasoning flow: analysis (Investigate & Note) and solve (Plan, Solve, Check, and Format) targets, dynamically selecting tier models.
                </p>
                <div className="grid gap-2.5 sm:grid-cols-3 pt-2">
                  {suggestedPrompts.map((p, i) => (
                    <div
                      key={i}
                      onClick={() => setText(p)}
                      className="rounded-lg border border-zinc-900 hover:border-zinc-800 bg-zinc-950/40 p-3 text-[11px] text-zinc-500 hover:text-zinc-350 cursor-pointer transition select-none"
                    >
                      "{p}"
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Text Composer Form */}
            {state === "idle" && (
              <div className="rounded-xl border border-zinc-900 bg-zinc-950 p-4 space-y-4 shadow-lg select-none">
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Ask conceptual questions about your sources..."
                  rows={4}
                  aria-label="Ask conceptual questions about your sources"
                  className="w-full rounded-lg border border-zinc-900 bg-zinc-950/20 px-3 py-2 text-xs md:text-sm text-zinc-100 placeholder-zinc-700 focus:outline-none focus:border-indigo-650 font-sans leading-relaxed resize-none"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />

                <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-zinc-900/60">
                  {/* Select Retrieval Pipe */}
                  <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-900 rounded-lg px-2 py-1 text-zinc-400 text-[10px]">
                    <ArrowRightLeft className="h-3 w-3 text-zinc-400" />
                    <select
                      value={retrieval}
                      onChange={(e) => setRetrieval(e.target.value as SolveQuery["retrieval_pipeline"])}
                      aria-label="Select retrieval pipeline"
                      className="bg-transparent border-0 p-0 text-[10px] font-semibold text-zinc-300 focus:outline-none cursor-pointer"
                    >
                      <option value="tree">PageIndex Tree</option>
                      <option value="hybrid">Hybrid (Vec+Key)</option>
                      <option value="naive">Naive Vector</option>
                      <option value="combined">Combined Pipeline</option>
                    </select>
                  </div>

                  {/* Select Solver Mode */}
                  <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-900 rounded-lg px-2 py-1 text-zinc-400 text-[10px]">
                    <Layers className="h-3 w-3 text-zinc-400" />
                    <select
                      value={mode}
                      onChange={(e) => setMode(e.target.value as SolveQuery["mode"])}
                      aria-label="Select solver mode"
                      className="bg-transparent border-0 p-0 text-[10px] font-semibold text-zinc-300 focus:outline-none cursor-pointer"
                    >
                      <option value="auto">Auto Mode</option>
                      <option value="detailed">Detailed Loop</option>
                      <option value="quick">Quick Synthesis</option>
                    </select>
                  </div>

                  <button
                    onClick={handleSend}
                    disabled={!text.trim()}
                    aria-label="Run solve mission"
                    className="ml-auto flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white font-bold text-xs px-4 py-2 transition"
                  >
                    <Zap className="h-3.5 w-3.5" />
                    <span>Run Solve Mission</span>
                  </button>
                </div>
              </div>
            )}

            {/* Active Streaming Pipeline loops */}
            {state === "streaming" && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 border-b border-zinc-900 pb-2">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500" />
                  </span>
                  <span className="text-xs uppercase font-extrabold tracking-widest text-zinc-400 font-mono">
                    Agent Solve Pipeline Ingress
                  </span>
                </div>
                
                <div className="space-y-3">
                  {steps.map((step, i) => {
                    const meta = agentMeta[step.agent] || agentMeta.manager;
                    const Icon = meta.icon;
                    const isLatest = i === steps.length - 1;
                    const isExpanded = expandedStepIndex === i || isLatest;

                    return (
                      <div
                        key={i}
                        className={`rounded-xl border transition-all duration-300 ${
                          isLatest
                            ? `border-l-4 border-l-indigo-500 ${meta.border} ${meta.bg}`
                            : `border-zinc-900 bg-zinc-950/40`
                        }`}
                      >
                        <div 
                          onClick={() => setExpandedStepIndex(expandedStepIndex === i ? null : i)}
                          className="flex items-center justify-between px-4 py-3 cursor-pointer select-none"
                          role="button"
                          aria-expanded={expandedStepIndex === i}
                          tabIndex={0}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedStepIndex(expandedStepIndex === i ? null : i); } }}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <Icon className={`h-4.5 w-4.5 shrink-0 ${meta.color}`} />
                            <div className="min-w-0">
                              <div className="text-xs font-bold text-zinc-200">{meta.label}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {isLatest && (
                              <span className="text-[9px] font-mono text-indigo-400 font-extrabold uppercase bg-indigo-950/40 border border-indigo-900/30 px-1.5 py-0.5 rounded animate-pulse">
                                Processing...
                              </span>
                            )}
                            {isExpanded ? <ChevronDown className="h-4 w-4 text-zinc-500" /> : <ChevronRight className="h-4 w-4 text-zinc-500" />}
                          </div>
                        </div>

                        {isExpanded && (
                          <div className="px-4 pb-4 pt-1 border-t border-zinc-900/60 select-text">
                            <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-zinc-400 bg-zinc-950/80 rounded-lg p-3 border border-zinc-900/40 max-h-60 overflow-auto">
                              {step.content || "Accumulating delta thoughts..."}
                            </pre>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Error banner */}
            {state === "error" && (
              <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 space-y-3">
                <div className="flex items-center gap-2 text-red-400">
                  <AlertCircle className="h-5 w-5" />
                  <span className="font-bold text-xs uppercase font-mono">Solve Execution Failed</span>
                </div>
                <p className="text-xs text-zinc-400 leading-normal select-text">
                  {errorMsg}
                </p>
                <button
                  onClick={() => setState("idle")}
                  aria-label="Dismiss error"
                  className="rounded-lg border border-red-800 bg-red-950/50 px-3 py-1.5 text-xs text-red-300 hover:bg-red-900 transition"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Complete: final answer sheet */}
            {state === "complete" && answer && (
              <div className="space-y-5 animate-slide-in">
                
                {/* Response Sheet */}
                <div className="rounded-xl border border-zinc-900 bg-zinc-950 shadow-2xl p-6 space-y-5 select-text">
                  
                  {/* Synthesis header details */}
                  <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
                    <span className="text-xs uppercase font-extrabold text-indigo-400 tracking-wider font-mono flex items-center gap-1.5 select-none">
                      <Sparkles className="h-4 w-4 text-indigo-400" />
                      Synthesis Output
                    </span>
                    <button
                      onClick={() => copyToClipboard(answer.answer)}
                      aria-label="Copy as markdown"
                      className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-300 transition select-none"
                    >
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy MD</span>
                    </button>
                  </div>

                  {/* Markdown */}
                  <div className="prose prose-invert prose-xs md:prose-sm max-w-none prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-zinc-900 prose-code:text-indigo-400 leading-relaxed select-text">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {answer.answer}
                    </ReactMarkdown>
                  </div>

                  {/* Detailed citations list */}
                  {citations.length > 0 && (
                    <div className="space-y-2.5 pt-4 border-t border-zinc-900/60 select-none">
                      <span className="text-[10px] uppercase font-bold text-zinc-400 font-mono tracking-wider block">
                        Citations References ({citations.length})
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {citations.map((c, i) => (
                          <div
                            key={i}
                            className="flex items-center gap-1.5 bg-indigo-950/15 border border-indigo-900/30 text-[9px] text-indigo-300 px-3 py-1 rounded-full font-mono"
                          >
                            <FileText className="h-3 w-3 shrink-0" />
                            <span>{c.doc_id.split("/").pop()}</span>
                            <span className="text-indigo-500 font-bold">p.{c.page}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Artifact directory block */}
                  {answer.solve_dir && (
                    <div className="flex justify-between items-center text-[10px] font-mono text-zinc-500 pt-2 border-t border-zinc-900/40 select-none">
                      <span>Artifact Folder: {answer.solve_dir}</span>
                      {(answer as any).metadata && (
                        <div className="flex items-center gap-3">
                          <span>Elapsed: {(answer as any).metadata.elapsed_seconds}s</span>
                          <span>Score: {(answer as any).metadata.complexity_score?.toFixed(2)}</span>
                          <span className="text-indigo-400 uppercase">{(answer as any).metadata.model_used}</span>
                        </div>
                      )}
                    </div>
                  )}

                </div>

                <button
                  onClick={() => {
                    setState("idle");
                    setSteps([]);
                    setAnswer(null);
                    setCitations([]);
                  }}
                  aria-label="Start new solve session"
                  className="rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-zinc-300 font-semibold text-xs px-4 py-2 transition"
                >
                  New Solve Session
                </button>

              </div>
            )}

          </div>
        </div>
      </main>

      {/* ─── RIGHT COLUMN: PageIndex Tree Browser ─── */}
      {showRightSidebar && (
        <aside className="w-80 shrink-0 border-l border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <Layers className="h-4 w-4 text-indigo-400 animate-pulse" />
              Reasoning Index
            </span>
          </div>

          {/* Search tree input */}
          <div className="p-3 border-b border-zinc-900/60">
            <div className="relative flex items-center border border-zinc-900 bg-zinc-950 rounded-lg p-1.5">
              <Search className="h-3.5 w-3.5 text-zinc-600 ml-1 shrink-0" />
              <input
                type="text"
                placeholder="Search index headings..."
                value={treeSearch}
                onChange={(e) => setTreeSearch(e.target.value)}
                aria-label="Search index headings"
                className="flex-1 bg-transparent border-0 px-2 py-0 text-xs text-zinc-300 placeholder-zinc-700 focus:outline-none focus:ring-0"
              />
              {treeSearch && (
                <button onClick={() => setTreeSearch("")} aria-label="Clear search" className="text-zinc-600 hover:text-zinc-400">
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Render collapsible tree hierarchy */}
          <div className="flex-1 overflow-y-auto p-3.5 space-y-1">
            {loadingTree ? (
              <div className="flex flex-col items-center justify-center py-12 text-zinc-600 text-xs gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
                <span>Loading index tree...</span>
              </div>
            ) : !selectedDocId ? (
              <div className="rounded-lg border border-dashed border-zinc-900 p-6 text-center text-zinc-500 text-xs">
                Select a document from left panel to view index tree.
              </div>
            ) : !indexTree ? (
              <div className="rounded-lg border border-dashed border-zinc-900 p-6 text-center text-zinc-500 text-xs">
                PageIndex tree unavailable for this document.
              </div>
            ) : filteredTree ? (
              <div className="space-y-0.5 pr-1">
                <TreeItem node={filteredTree} depth={0} />
              </div>
            ) : (
              <div className="text-center py-8 text-zinc-600 text-xs">
                No matching headings found.
              </div>
            )}
          </div>
          
          <div className="p-4 border-t border-zinc-900 bg-zinc-950/40 text-[10px] text-zinc-500 font-mono">
            PageIndex Explorer
          </div>
        </aside>
      )}

      {/* Toast Notification Container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none select-none" role="status" aria-live="polite">
        {successMsg && (
          <div className="rounded-lg border border-emerald-900 bg-emerald-950/80 backdrop-blur-md px-4 py-3 text-xs text-emerald-400 flex items-center gap-2 pointer-events-auto shadow-lg">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span>{successMsg}</span>
          </div>
        )}
        {errorMsg && (
          <div className="rounded-lg border border-red-900 bg-red-950/80 backdrop-blur-md px-4 py-3 text-xs text-red-400 flex items-center gap-2 pointer-events-auto shadow-lg">
            <AlertCircle className="h-4 w-4 text-red-400" />
            <span className="select-text">{errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} aria-label="Dismiss error" className="ml-auto text-red-500 hover:text-red-400">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

    </div>
  );
}
