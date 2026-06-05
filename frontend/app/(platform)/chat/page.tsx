"use client";

import { useState, useRef, useEffect, type FormEvent, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useUploadPolling } from "@/lib/use-upload-polling";
import { 
  Send, 
  Trash2, 
  Brain, 
  Sparkles, 
  Database, 
  Plus, 
  Trash, 
  Copy, 
  BookOpen, 
  Layers, 
  ArrowRightLeft, 
  AlertCircle, 
  RefreshCw, 
  X, 
  Lightbulb, 
  BookMarked, 
  Save,
  CheckCircle2, 
  ChevronRight, 
  ChevronDown,
  Upload,
  FileText,
  Square,
  CheckSquare,
  PanelLeft,
  PanelRight,
  User,
  ExternalLink,
  Loader2
} from "lucide-react";
import { useWebSocket } from "@/providers/websocket-provider";
import type { SolveQuery, Citation } from "@/types/api";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import { Badge } from "@/components/ui/badge";
import { uploadDocument, pollUploadTask, fetchKnowledgeBases, type KnowledgeBase } from "@/lib/knowledge";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  steps?: Record<string, string>;
  citations?: Citation[];
  modelUsed?: string;
  complexityScore?: number;
  targetTier?: string;
  elapsedSeconds?: number;
}

type DocumentInfo = {
  doc_id: string;
  page_count?: number;
  status: "indexed" | "processing" | "failed";
};

type NotebookNote = {
  id: string;
  content: string;
  source: string;
  timestamp: number;
};

type Notebook = {
  id: string;
  title: string;
  description: string;
  notes: NotebookNote[];
  created_at: number;
  updated_at: number;
};

const STORAGE_KEY = "udip_chat_history";

export default function ChatPage() {
  const { solveStatus, send, subscribe } = useWebSocket();
  
  // Layout views
  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightSidebar, setShowRightSidebar] = useState(true);

  // Chat thread states
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingSteps, setStreamingSteps] = useState<Record<string, string>>({});
  const [streamingAgent, setStreamingAgent] = useState<string | null>(null);
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [activeAccordion, setActiveAccordion] = useState<boolean>(true);
  const [expandedThoughtIndex, setExpandedThoughtIndex] = useState<string | null>(null);
  
  // Scopes & Sources (Left Panel)
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [selectedKb, setSelectedKb] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [retrievalMode, setRetrievalMode] = useState<SolveQuery["retrieval_pipeline"]>("tree");
  const [solveMode, setSolveMode] = useState<SolveQuery["mode"]>("auto");
  
  // Drag & drop upload
  const [dragging, setDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [activeUploadTaskId, setActiveUploadTaskId] = useState<string | null>(null);
  const [pendingUploadName, setPendingUploadName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // The previous polling block had a memory leak: it created a setInterval
  // inside an async handler and only cleared it on complete/failed — if
  // the user navigated away, the interval kept running forever. We now
  // drive polling through ``useUploadPolling`` which has proper cleanup
  // and a max-attempts guard.
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
      setErrorMsg(`Document parsing failed: ${name} (${task?.message ?? "unknown error"})`);
    },
    onError: () => {
      setUploadProgress(null);
      setActiveUploadTaskId(null);
      setPendingUploadName(null);
    },
  });

  // Notebooks & Synthesis (Right Panel)
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [selectedNbId, setSelectedNbId] = useState<string | null>(null);
  const [showCreateNbModal, setShowCreateNbModal] = useState(false);
  const [newNbTitle, setNewNbTitle] = useState("");
  const [newNbDesc, setNewNbDesc] = useState("");
  const [creatingNb, setCreatingNb] = useState(false);

  // Focus notebook title input when create modal opens
  useEffect(() => {
    if (showCreateNbModal) {
      const timer = setTimeout(() => {
        const input = document.querySelector<HTMLElement>(
          '[aria-label="Construct Notebook"] input[aria-label="Notebook title"]'
        );
        input?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [showCreateNbModal]);
  
  // Notes lists
  const [noteInput, setNoteInput] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  
  // Idea generation state
  const [selectedNotesForSynthesis, setSelectedNotesForSynthesis] = useState<Record<string, boolean>>({});
  const [isGeneratingIdeas, setIsGeneratingIdeas] = useState(false);
  const [generatedIdeas, setGeneratedIdeas] = useState<string[]>([]);
  const [ideaModel, setIdeaModel] = useState("Qwen3-1.7B-Q4_K_M");
  const [availableModels, setAvailableModels] = useState<any[]>([]);

  // Notifications / UI messages
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string>(crypto.randomUUID());

  // Load chat history and configurations on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) setMessages(JSON.parse(saved));
      } catch {}
    }
    loadKbs();
    loadNotebooks();
    loadModels();
  }, []);

  // Save chat history (debounced — avoids writing on every keystroke)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
      } catch {}
    }, 500);
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
  }, [messages]);

  // Scroll to bottom on stream / new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingAnswer, streamingSteps]);

  // Load knowledge bases
  const loadKbs = async () => {
    try {
      const bases = await fetchKnowledgeBases();
      if (bases && bases.length > 0) {
        setKbs(bases);
        if (!selectedKb) {
          setSelectedKb(bases[0].name);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Load documents inside selected KB
  const loadDocuments = useCallback(async (kbName: string) => {
    if (!kbName) {
      setDocuments([]);
      return;
    }
    setLoadingDocs(true);
    try {
      const res = await secureFetch(`${API_BASE_URL}/knowledge/${encodeURIComponent(kbName)}/documents`);
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

  // Load KBs documents on change
  useEffect(() => {
    loadDocuments(selectedKb);
  }, [selectedKb, loadDocuments]);

  // Load Notebooks
  const loadNotebooks = async () => {
    try {
      const res = await secureFetch(`${API_BASE_URL}/notebooks`);
      if (res.ok) {
        const data = await res.json();
        setNotebooks(data);
        if (data.length > 0 && !selectedNbId) {
          setSelectedNbId(data[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Load Models
  const loadModels = async () => {
    try {
      const res = await secureFetch(`${API_BASE_URL}/models`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setAvailableModels(data);
        }
      }
    } catch {}
  };

  // Subscriptions to Websocket Events
  useEffect(() => {
    return subscribe("agent_step", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      const agent = data.agent as string;
      const delta = data.delta as string || data.content as string || "";
      
      setStreamingAgent(agent);
      if (agent === "format") {
        setStreamingAnswer((prev) => prev + delta);
      } else {
        setStreamingSteps((prev) => {
          const existing = prev[agent] || "";
          return {
            ...prev,
            [agent]: existing + delta
          };
        });
      }
    });
  }, [subscribe]);

  useEffect(() => {
    return subscribe("complete", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      
      const completeAnswer = (data as any).answer || streamingAnswer;
      const meta = (data as any).metadata || {};
      
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: completeAnswer,
          timestamp: Date.now(),
          steps: streamingSteps,
          citations: (data as any).citations || [],
          modelUsed: meta.model_used,
          complexityScore: meta.complexity_score,
          targetTier: meta.target_tier,
          elapsedSeconds: meta.elapsed_seconds
        },
      ]);
      
      setStreamingSteps({});
      setStreamingAgent(null);
      setStreamingAnswer("");
      setIsStreaming(false);
    });
  }, [subscribe, streamingAnswer, streamingSteps]);

  useEffect(() => {
    return subscribe("error", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      setIsStreaming(false);
      setErrorMsg((data as any).message || "AI Synthesizer pipeline failed.");
    });
  }, [subscribe]);

  // Handle send message
  const handleSend = (textToSend: string) => {
    if (!textToSend.trim() || isStreaming) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: textToSend.trim(),
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);

    setIsStreaming(true);
    setStreamingAnswer("");
    setStreamingSteps({});
    setStreamingAgent(null);
    setErrorMsg(null);
    sessionIdRef.current = crypto.randomUUID();

    const query: SolveQuery = {
      query: textToSend.trim(),
      kb_name: selectedKb,
      mode: solveMode,
      retrieval_pipeline: retrievalMode,
    };
    
    send({ ...query, session_id: sessionIdRef.current } as unknown as Record<string, unknown>);
    setInput("");
  };

  const onSubmitForm = (e: FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  const clearChat = () => {
    setMessages([]);
    setStreamingAnswer("");
    setStreamingSteps({});
    setStreamingAgent(null);
    setIsStreaming(false);
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
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
    if (!selectedKb) {
      setErrorMsg("Please select or create a Knowledge Base scope first.");
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
      setErrorMsg("Supported document formats: PDF, TXT, MD");
      return;
    }

    setUploadProgress(file.name);
    setErrorMsg(null);

    const result = await uploadDocument(file, selectedKb);
    if (result && result.task_id) {
      setPendingUploadName(file.name);
      setActiveUploadTaskId(result.task_id);
    } else {
      setUploadProgress(null);
      setErrorMsg("Failed to initiate file ingestion.");
    }
  };

  // Create Notebook
  const handleCreateNotebook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNbTitle.trim()) return;

    setCreatingNb(true);
    setErrorMsg(null);
    try {
      const res = await secureFetch(`${API_BASE_URL}/notebooks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newNbTitle, description: newNbDesc }),
      });

      if (!res.ok) throw new Error("Failed to construct notebook schema.");
      const data = await res.json();
      setNotebooks((prev) => [...prev, data]);
      setSelectedNbId(data.id);
      setNewNbTitle("");
      setNewNbDesc("");
      setShowCreateNbModal(false);
      setSuccessMsg("Notebook constructed successfully.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to construct notebook.");
    } finally {
      setCreatingNb(false);
    }
  };

  // Save manually typed note to active Notebook
  const handleSaveNote = async () => {
    if (!selectedNbId || !noteInput.trim()) return;

    setSavingNote(true);
    setErrorMsg(null);
    try {
      const res = await secureFetch(`${API_BASE_URL}/notebooks/${selectedNbId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: noteInput.trim() }),
      });

      if (!res.ok) throw new Error("Failed to write note.");
      await loadNotebooks();
      setNoteInput("");
      setSuccessMsg("Research note saved.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to write note.");
    } finally {
      setSavingNote(false);
    }
  };

  // Save Assistant Reply directly to Active Notebook
  const handleSaveMessageToNotebook = async (text: string) => {
    if (!selectedNbId) {
      setErrorMsg("Please select or construct a Notebook in the right panel first.");
      return;
    }

    try {
      const res = await secureFetch(`${API_BASE_URL}/notebooks/${selectedNbId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text, source: "chat" }),
      });

      if (!res.ok) throw new Error("Save note failed.");
      await loadNotebooks();
      setSuccessMsg("Added chat response to Notebook.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to append note.");
    }
  };

  // Trigger idea generation synthesis
  const handleSynthesizeProposals = async () => {
    const activeNb = notebooks.find((n) => n.id === selectedNbId);
    if (!activeNb || activeNb.notes.length === 0) {
      setErrorMsg("Add notes or save responses to this Notebook before synthesis.");
      return;
    }

    setIsGeneratingIdeas(true);
    setErrorMsg(null);
    setGeneratedIdeas([]);
    try {
      const res = await secureFetch(`${API_BASE_URL}/ideagen/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          notebook_ids: [selectedNbId],
          model_id: ideaModel,
        }),
      });

      if (!res.ok) throw new Error("Synthesis service failed.");
      const data = await res.json();
      setGeneratedIdeas(data.ideas || []);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to generate conceptual links.");
    } finally {
      setIsGeneratingIdeas(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSuccessMsg("Copied reply markdown to clipboard.");
    setTimeout(() => setSuccessMsg(null), 2500);
  };

  const activeNotebook = notebooks.find((n) => n.id === selectedNbId);

  // Suggested prompt cards
  const suggestionCards = [
    {
      title: "Summarize Workspace",
      desc: "Distill the core conceptual claims and indexing highlights.",
      icon: BookOpen,
      prompt: "Generate a comprehensive summary of all materials loaded in our active Knowledge Base workspace."
    },
    {
      title: "Synthesize Gaps",
      desc: "Uncover missing links or contradictory statements.",
      icon: Sparkles,
      prompt: "Analyze the active indexed documents and synthesize any potential research gaps or unproven arguments."
    },
    {
      title: "Compare Architectures",
      desc: "Assess differing formulas, metrics, or methods.",
      icon: Layers,
      prompt: "Find and compare the core methodologies or technical architectures discussed in these documents."
    }
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
            {/* KB selector */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Active Knowledge Base
              </label>
              <select
                value={selectedKb}
                onChange={(e) => setSelectedKb(e.target.value)}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans"
                aria-label="Select active knowledge base"
              >
                {kbs.length === 0 ? (
                  <option value="">No KBs (Upload to create)</option>
                ) : (
                  kbs.map((kb) => (
                    <option key={kb.name} value={kb.name}>{kb.name}</option>
                  ))
                )}
              </select>
            </div>

            {/* Upload Zone */}
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
                      <p className="text-xs text-zinc-300 font-medium">Drag & Drop file</p>
                      <p className="text-[10px] text-zinc-500 mt-0.5">PDF, TXT or MD (Local)</p>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* Document list */}
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
                          <p className="text-xs text-zinc-300 truncate font-medium" title={doc.doc_id}>
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
      )}

      {/* ─── CENTER COLUMN: Chat Thread & Composer ─── */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950 relative select-text">
        
        {/* Chat Control Toolbar */}
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-900 bg-zinc-950/40 px-4 select-none">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowLeftSidebar(!showLeftSidebar)}
              className={`p-1.5 rounded-lg border transition ${
                showLeftSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
              title="Toggle Sources Sidebar"
              aria-label="Toggle sources sidebar"
              aria-expanded={showLeftSidebar}
            >
              <PanelLeft className="h-4 w-4" />
            </button>
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <span className="text-xs font-semibold text-zinc-200 font-mono">Chat Lab</span>
          </div>

          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="flex items-center gap-1.5 rounded-lg border border-zinc-900 hover:border-zinc-850 hover:bg-zinc-900/35 px-2.5 py-1 text-xs text-zinc-500 hover:text-zinc-300 transition"
                aria-label="Clear chat thread"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Clear Thread</span>
              </button>
            )}
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <button
              onClick={() => setShowRightSidebar(!showRightSidebar)}
              className={`p-1.5 rounded-lg border transition ${
                showRightSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
              title="Toggle Notebook Panel"
              aria-label="Toggle notebook panel"
              aria-expanded={showRightSidebar}
            >
              <PanelRight className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Message Thread Scroll View */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          
          {/* Welcome Screen (If thread is empty) */}
          {messages.length === 0 && !streamingAnswer && !streamingAgent && (
            <div className="max-w-2xl mx-auto py-12 md:py-20 space-y-8 select-none">
              <div className="text-center space-y-4">
                <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 shadow-inner">
                  <Brain className="h-6 w-6 animate-pulse" />
                </div>
                <h2 className="text-2xl md:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-zinc-100 via-indigo-200 to-zinc-400 bg-clip-text text-transparent">
                  Scribble. Upload. Synthesize.
                </h2>
                <p className="text-xs md:text-sm text-zinc-500 max-w-md mx-auto leading-relaxed">
                  Ask questions about your loaded documents. The multi-agent pipeline will analyze references, reason recursively, and write answers into notes.
                </p>
              </div>

              {/* Suggestion Grid */}
              <div className="grid gap-3 sm:grid-cols-3" role="group" aria-label="Suggested prompts">
                {suggestionCards.map((card) => {
                  const Icon = card.icon;
                  return (
                    <button
                      key={card.title}
                      type="button"
                      onClick={() => handleSend(card.prompt)}
                      className="group flex flex-col justify-between rounded-xl border border-zinc-900 bg-zinc-950/40 p-4 transition text-left cursor-pointer hover:border-indigo-500/20 hover:bg-indigo-950/5 hover:-translate-y-0.5 focus:outline-none focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/30"
                    >
                      <Icon className="h-4.5 w-4.5 text-zinc-500 group-hover:text-indigo-400 transition" />
                      <div className="mt-4">
                        <div className="text-xs font-bold text-zinc-350">{card.title}</div>
                        <div className="text-[10px] text-zinc-500 mt-1 line-clamp-2 leading-normal">
                          {card.desc}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Render Thread Messages */}
          {messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                className={`flex gap-3 md:gap-4 max-w-3xl mx-auto ${isUser ? "justify-end" : "justify-start"}`}
              >
                {/* Avatar Icon */}
                {!isUser && (
                  <div className="h-7 w-7 rounded-lg bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0 select-none">
                    <Brain className="h-4.5 w-4.5" />
                  </div>
                )}

                <div className="flex flex-col gap-2 min-w-0 max-w-[85%]">
                  <div
                    className={`rounded-2xl px-4.5 py-3 shadow-inner ${
                      isUser
                        ? "bg-indigo-600/20 border border-indigo-500/30 text-zinc-150"
                        : "bg-zinc-900/40 border border-zinc-900/80 text-zinc-300"
                    }`}
                  >
                    {isUser ? (
                      <p className="text-xs md:text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    ) : (
                      <div className="space-y-4">
                        
                        {/* A. Collapsible Thought Process Accordion */}
                        {msg.steps && Object.keys(msg.steps).length > 0 && (
                          <div className="border border-zinc-900/60 rounded-lg overflow-hidden bg-zinc-950/30">
                            <button
                              type="button"
                              onClick={() => setExpandedThoughtIndex(expandedThoughtIndex === msg.id ? null : msg.id)}
                              className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-mono text-zinc-500 hover:text-zinc-300 transition focus:outline-none"
                              aria-label="Toggle multi-agent steps"
                              aria-expanded={expandedThoughtIndex === msg.id}
                            >
                              <span className="flex items-center gap-1.5 uppercase font-bold tracking-wider">
                                <CheckSquare className="h-3.5 w-3.5 text-emerald-500" />
                                Multi-Agent Steps ({Object.keys(msg.steps).length})
                              </span>
                              {expandedThoughtIndex === msg.id ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                            </button>
                            {expandedThoughtIndex === msg.id && (
                              <div className="px-3 pb-3 pt-0 border-t border-zinc-900/40 max-h-60 overflow-y-auto space-y-2.5">
                                {Object.entries(msg.steps).map(([agent, txt]) => (
                                  <div key={agent} className="text-[10px] font-mono border-l-2 border-zinc-800 pl-2 leading-relaxed">
                                    <span className="font-extrabold uppercase text-indigo-400">{agent}:</span>
                                    <p className="text-zinc-450 mt-0.5 whitespace-pre-wrap">{txt}</p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* B. Answer markdown body */}
                        <div className="prose prose-invert prose-xs md:prose-sm max-w-none prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-zinc-900 prose-code:text-indigo-400 prose-a:text-indigo-400 select-text leading-relaxed">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>

                        {/* C. Citations node references */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-2 border-t border-zinc-900/30">
                            {msg.citations.map((cit, idx) => (
                              <div
                                key={idx}
                                className="flex items-center gap-1 bg-indigo-950/15 border border-indigo-900/30 text-[9px] text-indigo-300 font-mono px-2 py-0.5 rounded-full"
                              >
                                <FileText className="h-2.5 w-2.5 shrink-0" />
                                <span>{cit.doc_id.split("/").pop()}</span>
                                <span className="text-indigo-500">p.{cit.page}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Message Action row */}
                  {!isUser && (
                    <div className="flex items-center gap-3 px-1 text-[10px] text-zinc-500 select-none">
                      <button
                        onClick={() => copyToClipboard(msg.content)}
                        className="flex items-center gap-1 hover:text-zinc-300 transition"
                        title="Copy text"
                        aria-label="Copy response"
                      >
                        <Copy className="h-3 w-3" />
                        <span>Copy</span>
                      </button>
                      <span className="h-3 w-[1px] bg-zinc-850" />
                      <button
                        onClick={() => handleSaveMessageToNotebook(msg.content)}
                        className="flex items-center gap-1 hover:text-zinc-300 transition text-indigo-400/80 hover:text-indigo-300"
                        title="Save response as note in active Notebook"
                        aria-label="Save to notebook"
                      >
                        <Save className="h-3 w-3" />
                        <span>Save to Notebook</span>
                      </button>
                      
                      {/* Telemetry info */}
                      {msg.modelUsed && (
                        <>
                          <span className="h-3 w-[1px] bg-zinc-850" />
                          <span className="font-mono text-[9px] text-zinc-600 truncate max-w-[120px]">
                            {msg.modelUsed}
                          </span>
                        </>
                      )}
                      {msg.elapsedSeconds != null && (
                        <>
                          <span className="h-3 w-[1px] bg-zinc-850" />
                          <span className="font-mono text-[9px] text-zinc-600">
                            {msg.elapsedSeconds}s
                          </span>
                        </>
                      )}
                    </div>
                  )}
                </div>

                {isUser && (
                  <div className="h-7 w-7 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400 shrink-0 select-none">
                    <User className="h-4.5 w-4.5" />
                  </div>
                )}
              </div>
            );
          })}

          {/* Active Streaming Thinking & Output */}
          {isStreaming && (
            <div className="flex gap-3 md:gap-4 max-w-3xl mx-auto justify-start animate-pulse">
              <div className="h-7 w-7 rounded-lg bg-indigo-650/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0 select-none animate-spin">
                <RefreshCw className="h-4.5 w-4.5" />
              </div>
              <div className="flex-1 flex flex-col gap-2 min-w-0 max-w-[85%]">
                <div className="rounded-2xl border border-indigo-900/35 bg-indigo-950/5 px-4.5 py-3.5 space-y-4">
                  
                  {/* Thought process display during stream */}
                  <div className="border border-indigo-900/20 rounded-lg overflow-hidden bg-zinc-950/40">
                    <button
                      type="button"
                      onClick={() => setActiveAccordion(!activeAccordion)}
                      className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-mono text-indigo-400 focus:outline-none"
                      aria-label="Toggle solving pipeline details"
                      aria-expanded={activeAccordion}
                    >
                      <span className="flex items-center gap-1.5 uppercase font-bold tracking-wider">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Solving Pipeline Live...
                      </span>
                      {activeAccordion ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                    </button>
                    {activeAccordion && (
                      <div className="px-3 pb-3 pt-0 border-t border-indigo-900/10 max-h-60 overflow-y-auto space-y-2.5">
                        {Object.entries(streamingSteps).map(([agent, txt]) => (
                          <div key={agent} className="text-[10px] font-mono border-l-2 border-indigo-850 pl-2 leading-relaxed">
                            <span className="font-extrabold uppercase text-indigo-300">{agent}:</span>
                            <p className="text-zinc-500 mt-0.5 whitespace-pre-wrap">{txt}</p>
                          </div>
                        ))}
                        {streamingAgent && streamingAgent !== "format" && (
                          <div className="text-[10px] font-mono border-l-2 border-amber-800 pl-2 leading-relaxed animate-pulse">
                            <span className="font-extrabold uppercase text-amber-500">{streamingAgent} thinking:</span>
                            <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500 ml-1.5" />
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Render streaming formatted text */}
                  {streamingAnswer && (
                    <div className="prose prose-invert prose-xs md:prose-sm max-w-none prose-code:text-indigo-400 select-text leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {streamingAnswer}
                      </ReactMarkdown>
                      <span className="inline-block h-2 w-2 rounded-full bg-indigo-500 animate-ping ml-1" />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Dynamic Composer Footer Box */}
        <footer className="border-t border-zinc-900/80 bg-zinc-950/80 p-4 shrink-0 select-none">
          <form onSubmit={onSubmitForm} className="max-w-3xl mx-auto space-y-3.5">
            <div className="relative flex items-end border border-zinc-900 bg-zinc-950/30 rounded-2xl p-2 focus-within:border-zinc-800 shadow-md">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={isStreaming ? "Thinking loop running..." : "Ask conceptual questions about your sources..."}
                disabled={isStreaming}
                rows={1}
                className="flex-1 max-h-40 min-h-10 rounded-xl border-0 bg-transparent px-3 py-2 text-xs md:text-sm text-zinc-100 placeholder-zinc-700 focus:outline-none focus:ring-0 disabled:opacity-50 resize-none leading-relaxed"
                aria-label="Ask a question"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    onSubmitForm(e);
                  }
                }}
              />
              <button
                type="submit"
                disabled={isStreaming || !input.trim()}
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition duration-300 ${
                  isStreaming || !input.trim()
                    ? "bg-zinc-900 text-zinc-750 cursor-not-allowed"
                    : "bg-indigo-650 hover:bg-indigo-650 hover:opacity-90 text-white shadow-lg shadow-indigo-600/10 cursor-pointer"
                }`}
                aria-label="Send message"
              >
                <Send className="h-4.5 w-4.5" />
              </button>
            </div>

            {/* Composer selector pills */}
            <div className="flex flex-wrap items-center gap-2 text-[10px]">
              {/* Retrieval Pipeline Pill */}
              <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-900 rounded-lg px-2.5 py-1 text-zinc-400">
                <ArrowRightLeft className="h-3 w-3 text-zinc-400" />
                <span className="font-mono text-[9px] uppercase text-zinc-400 mr-0.5">Pipe</span>
                <select
                  value={retrievalMode}
                  onChange={(e) => setRetrievalMode(e.target.value as SolveQuery["retrieval_pipeline"])}
                  className="bg-transparent border-0 p-0 text-[10px] font-semibold text-zinc-300 focus:outline-none focus:ring-0 cursor-pointer"
                  aria-label="Select retrieval pipeline"
                >
                  <option value="tree">PageIndex Tree</option>
                  <option value="hybrid">Hybrid (Vec+Key)</option>
                  <option value="naive">Naive Vector</option>
                  <option value="combined">Combined Pipeline</option>
                </select>
              </div>

              {/* Solve Mode Pill */}
              <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-900 rounded-lg px-2.5 py-1 text-zinc-400">
                <Layers className="h-3 w-3 text-zinc-400" />
                <span className="font-mono text-[9px] uppercase text-zinc-400 mr-0.5">Mode</span>
                <select
                  value={solveMode}
                  onChange={(e) => setSolveMode(e.target.value as SolveQuery["mode"])}
                  className="bg-transparent border-0 p-0 text-[10px] font-semibold text-zinc-300 focus:outline-none focus:ring-0 cursor-pointer"
                  aria-label="Select solve mode"
                >
                  <option value="auto">Auto Model</option>
                  <option value="detailed">Detailed Loop</option>
                  <option value="quick">Quick Cascade</option>
                </select>
              </div>

              {solveStatus === "closed" && (
                <div className="flex items-center gap-1 text-amber-500 font-mono text-[9px] ml-auto">
                  <AlertCircle className="h-3.5 w-3.5" />
                  <span>WS OFFLINE</span>
                </div>
              )}
            </div>
          </form>
        </footer>
      </main>

      {/* ─── RIGHT COLUMN: NotebookLM Notes & Ideas ─── */}
      {showRightSidebar && (
        <aside className="w-80 shrink-0 border-l border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <BookMarked className="h-4 w-4 text-indigo-400" />
              Notebook Annotations
            </span>
            <button
              onClick={() => setShowCreateNbModal(true)}
              className="p-1 rounded-lg border border-zinc-900 hover:border-zinc-800 text-zinc-400 hover:text-white transition"
              title="Construct Notebook"
              aria-label="Open construct notebook"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            
            {/* Notebook selection */}
            <div className="space-y-1.5">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Target Notebook
              </label>
              <select
                value={selectedNbId || ""}
                onChange={(e) => setSelectedNbId(e.target.value || null)}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans"
                aria-label="Select target notebook"
              >
                {notebooks.length === 0 ? (
                  <option value="">No Notebooks</option>
                ) : (
                  notebooks.map((nb) => (
                    <option key={nb.id} value={nb.id}>{nb.title}</option>
                  ))
                )}
              </select>
            </div>

            {/* Note Cards Timeline */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Notes Timeline ({activeNotebook?.notes.length || 0})
              </label>
              
              {!activeNotebook ? (
                <div className="rounded-lg border border-dashed border-zinc-900 p-6 text-center text-zinc-500 text-xs">
                  Create a notebook to capture thoughts.
                </div>
              ) : activeNotebook.notes.length === 0 ? (
                <div className="rounded-lg border border-dashed border-zinc-900 p-6 text-center text-zinc-500 text-xs">
                  Notebook is empty. Save response or write note below.
                </div>
              ) : (
                <div className="space-y-2.5 max-h-[220px] overflow-y-auto pr-1">
                  {activeNotebook.notes.map((note) => (
                    <div
                      key={note.id}
                      className="rounded-lg border border-zinc-900 bg-zinc-950/40 p-3 space-y-1.5 text-zinc-300 text-[11px] leading-relaxed relative"
                    >
                      <p className="whitespace-pre-wrap font-sans select-text">{note.content.substring(0, 200)}{note.content.length > 200 && "..."}</p>
                      <div className="flex items-center justify-between text-[9px] font-mono text-zinc-600 border-t border-zinc-900/60 pt-1.5 mt-1 select-none">
                        <span className="capitalize text-indigo-400">Src: {note.source}</span>
                        <span>{new Date(note.timestamp * 1000).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* In-page Note Editor */}
            {activeNotebook && (
              <div className="space-y-2.5 border-t border-zinc-900/60 pt-3">
                <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                  Add Research Note
                </label>
                <textarea
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  placeholder="Draft insights, paste quotes, or add custom conceptual highlights..."
                  rows={2}
                  disabled={savingNote}
                  className="w-full rounded-lg border border-zinc-850 bg-zinc-950 p-2.5 text-xs text-zinc-200 placeholder-zinc-700 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 resize-none font-sans"
                  aria-label="Draft note content"
                />
                <div className="flex justify-end select-none">
                  <button
                    onClick={handleSaveNote}
                    disabled={savingNote || !noteInput.trim()}
                    className="flex items-center gap-1.5 rounded-lg bg-zinc-100 px-3 py-1.5 text-[10px] font-bold text-zinc-900 hover:bg-white transition disabled:opacity-40"
                    aria-label="Save note"
                  >
                    {savingNote ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                    <span>Save Note</span>
                  </button>
                </div>
              </div>
            )}

            {/* Synthesizer Synthesis trigger */}
            {activeNotebook && activeNotebook.notes.length > 0 && (
              <div className="space-y-3.5 border-t border-zinc-900/60 pt-4">
                <div className="flex items-center gap-1 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono">
                  <Brain className="h-3.5 w-3.5 text-indigo-400 animate-pulse" />
                  <span>Synthesize Concept ideas</span>
                </div>

                <div className="space-y-2 select-text">
                  <label className="text-[9px] uppercase font-bold text-zinc-600 tracking-wider font-mono block">
                    Synthesis Model
                  </label>
                  <select
                    value={ideaModel}
                    onChange={(e) => setIdeaModel(e.target.value)}
                    className="w-full rounded-lg border border-zinc-900 bg-zinc-950 px-2.5 py-1.5 text-[10px] text-zinc-300 focus:outline-none"
                    aria-label="Select synthesis model"
                  >
                    {availableModels.length === 0 ? (
                      <>
                        <option value="Qwen3-1.7B-Q4_K_M">Qwen3-1.7B (Q4_K_M)</option>
                        <option value="Qwen3-8B">Qwen3-8B</option>
                      </>
                    ) : (
                      availableModels.map((m) => (
                        <option key={m.id} value={m.id}>{m.name} ({m.tier})</option>
                      ))
                    )}
                  </select>
                </div>

                <button
                  onClick={handleSynthesizeProposals}
                  disabled={isGeneratingIdeas}
                  className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600/20 border border-indigo-500/30 hover:bg-indigo-600/35 px-3 py-2 text-xs font-bold text-indigo-300 transition disabled:opacity-40"
                  aria-label="Generate project ideas"
                >
                  {isGeneratingIdeas ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Synthesizing...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-3.5 w-3.5" />
                      <span>Generate Project Ideas</span>
                    </>
                  )}
                </button>
              </div>
            )}
            
            {/* Generated Proposal cards */}
            {generatedIdeas.length > 0 && (
              <div className="space-y-2 border-t border-zinc-900/60 pt-4 animate-slide-in">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-emerald-400 font-mono flex items-center gap-1">
                    <Lightbulb className="h-3.5 w-3.5 text-emerald-400" />
                    Proposals Synthesized
                  </span>
                  <button onClick={() => setGeneratedIdeas([])} className="text-zinc-600 hover:text-zinc-400 text-xs" aria-label="Clear generated ideas">
                    Clear
                  </button>
                </div>
                <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                  {generatedIdeas.map((idea, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-emerald-950/60 bg-emerald-950/5 p-3 space-y-1 text-zinc-300 text-[11px] leading-relaxed relative"
                    >
                      <p className="font-semibold text-emerald-400">Proposal #{idx+1}</p>
                      <p className="select-text mt-1">{idea}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        </aside>
      )}

      {/* ─── GLOBAL MODALS & TOASTS ─── */}
      
      {/* Toast banners */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 select-none pointer-events-none max-w-sm" role="status" aria-live="polite">
        {successMsg && (
          <div className="rounded-lg border border-emerald-900 bg-emerald-950/80 backdrop-blur-md px-4 py-3 text-xs text-emerald-400 flex items-center gap-2 pointer-events-auto shadow-lg shadow-emerald-950/20">
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}
        {errorMsg && (
          <div className="rounded-lg border border-red-900 bg-red-950/80 backdrop-blur-md px-4 py-3 text-xs text-red-400 flex items-center gap-2 pointer-events-auto shadow-lg shadow-red-950/20">
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
            <span className="select-text">{errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} className="ml-auto text-red-500 hover:text-red-400" aria-label="Dismiss error">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Construct Notebook Modal */}
      {showCreateNbModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm select-none"
          role="dialog"
          aria-modal="true"
          aria-label="Construct Notebook"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setShowCreateNbModal(false);
            }
            if (e.key === "Tab") {
              const modal = e.currentTarget.querySelector("form");
              if (!modal) return;
              const focusable = modal.querySelectorAll<HTMLElement>(
                'input, textarea, button:not([disabled]), [tabindex]:not([tabindex="-1"])'
              );
              if (focusable.length === 0) return;
              const first = focusable[0];
              const last = focusable[focusable.length - 1];
              if (e.shiftKey) {
                if (document.activeElement === first) {
                  e.preventDefault();
                  last.focus();
                }
              } else {
                if (document.activeElement === last) {
                  e.preventDefault();
                  first.focus();
                }
              }
            }
          }}
        >
          <form
            onSubmit={handleCreateNotebook}
            className="w-full max-w-md rounded-xl border border-zinc-900 bg-zinc-950 p-6 space-y-4 shadow-xl"
          >
            <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-1.5 font-mono uppercase tracking-wider">
                <BookOpen className="h-4.5 w-4.5 text-indigo-400" />
                Construct Notebook
              </h3>
              <button
                type="button"
                onClick={() => setShowCreateNbModal(false)}
                className="text-zinc-500 hover:text-zinc-350 transition"
                aria-label="Close notebook modal"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>

            <div className="space-y-3 select-text">
              <div>
                <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono mb-1.5 block">
                  Notebook Title
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Quantum Ingestion Core"
                  value={newNbTitle}
                  onChange={(e) => setNewNbTitle(e.target.value)}
                  className="w-full rounded-lg border border-zinc-900 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none"
                  aria-label="Notebook title"
                />
              </div>

              <div>
                <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono mb-1.5 block">
                  Notebook Description
                </label>
                <textarea
                  placeholder="Summary of research themes, study guidelines or annotation references..."
                  rows={3}
                  value={newNbDesc}
                  onChange={(e) => setNewNbDesc(e.target.value)}
                  className="w-full rounded-lg border border-zinc-900 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none resize-none font-sans"
                  aria-label="Notebook description"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-zinc-900 pt-4">
              <button
                type="button"
                onClick={() => setShowCreateNbModal(false)}
                className="rounded-lg border border-zinc-900 px-4 py-1.5 text-xs font-semibold text-zinc-400 hover:bg-zinc-900 transition"
                aria-label="Cancel notebook creation"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creatingNb || !newNbTitle.trim()}
                className="flex items-center gap-1.5 rounded-lg bg-indigo-650 px-4 py-1.5 text-xs font-bold text-white hover:opacity-90 transition disabled:opacity-40"
                aria-label="Create notebook"
              >
                {creatingNb ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Creating...</span>
                  </>
                ) : (
                  <span>Construct</span>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

    </div>
  );
}
