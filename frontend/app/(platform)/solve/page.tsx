"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useUploadPolling } from "@/lib/use-upload-polling";
import { useWebSocket } from "@/providers/websocket-provider";
import type {
  SolveQuery,
  AgentStepFrame,
  Citation,
  CompleteFrame,
  IndexNode,
} from "@/types/api";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import { uploadDocument, pollUploadTask, fetchKnowledgeBases } from "@/lib/knowledge";
import { toast } from "sonner";
import { SourcesSidebar } from "@/components/solve/sources-sidebar";
import { SolveToolbar } from "@/components/solve/solve-toolbar";
import { SuggestedPrompts } from "@/components/solve/suggested-prompts";
import { SolveComposer } from "@/components/solve/solve-composer";
import { StreamingPipeline } from "@/components/solve/streaming-pipeline";
import { ErrorBanner } from "@/components/solve/error-banner";
import { SynthesisResult } from "@/components/solve/synthesis-result";
import { PageIndexSidebar } from "@/components/solve/page-index-sidebar";

type SolveState = "idle" | "streaming" | "complete" | "error";

type DocumentInfo = {
  doc_id: string;
  page_count?: number;
  status: "indexed" | "processing" | "failed";
};

export default function SolvePage() {
  const { solveStatus, send, subscribe } = useWebSocket();
  const [state, setState] = useState<SolveState>("idle");

  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightSidebar, setShowRightSidebar] = useState(true);

  const [steps, setSteps] = useState<AgentStepFrame[]>([]);
  const [expandedStepIndex, setExpandedStepIndex] = useState<number | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [answer, setAnswer] = useState<CompleteFrame | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  const [text, setText] = useState("");
  const [kbName, setKbName] = useState("");
  const [mode, setMode] = useState<SolveQuery["mode"]>("auto");
  const [retrieval, setRetrieval] = useState<SolveQuery["retrieval_pipeline"]>("tree");
  const [kbOptions, setKbOptions] = useState<{ value: string; label: string }[]>([
    { value: "", label: "(none)" },
  ]);

  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [activeUploadTaskId, setActiveUploadTaskId] = useState<string | null>(null);
  const [pendingUploadName, setPendingUploadName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

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
      toast.error(`Document parsing failed: ${name}`);
    },
    onError: () => {
      setUploadProgress(null);
      setActiveUploadTaskId(null);
      setPendingUploadName(null);
    },
  });

  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const [indexTree, setIndexTree] = useState<IndexNode | null>(null);
  const [loadingTree, setLoadingTree] = useState(false);
  const [treeSearch, setTreeSearch] = useState("");

  const sessionIdRef = useRef<string>(crypto.randomUUID());

  useEffect(() => {
    loadKbs();
  }, []);

  const loadKbs = async () => {
    try {
      const bases = await fetchKnowledgeBases();
      if (bases) {
        const mapped = bases.map((kb: unknown) => {
          const name =
            typeof kb === "string"
              ? kb
              : kb && typeof kb === "object" && "name" in kb
                ? String(kb.name)
                : "default";
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

  const loadDocuments = useCallback(
    async (kb: string) => {
      if (!kb) {
        setDocuments([]);
        setSelectedDocId("");
        setIndexTree(null);
        return;
      }
      setLoadingDocs(true);
      try {
        const res = await secureFetch(
          `${API_BASE_URL}/knowledge/${encodeURIComponent(kb)}/documents`
        );
        if (res.ok) {
          const data = await res.json();
          const list = Array.isArray(data) ? data : data.documents || [];
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
    },
    [selectedDocId]
  );

  useEffect(() => {
    loadDocuments(kbName);
  }, [kbName, loadDocuments]);

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

  useEffect(() => {
    return subscribe("agent_step", (data: Record<string, unknown>) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;

      const agentRaw = String(data.agent ?? "");
      const agent = agentRaw as AgentStepFrame["agent"];
      const delta = String(data.delta ?? data.content ?? "");
      const timestamp = Number(data.timestamp ?? Date.now() / 1000);

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
              agent,
              content: delta,
              timestamp: timestamp,
            },
          ];
        }
      });
    });
  }, [subscribe]);

  useEffect(() => {
    return subscribe("citation", (data: Record<string, unknown>) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      if (data.citation && typeof data.citation === "object") {
        setCitations((prev) => [...prev, data.citation as Citation]);
      }
    });
  }, [subscribe]);

  useEffect(() => {
    return subscribe("complete", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      setAnswer(data as CompleteFrame);
      setState("complete");
    });
  }, [subscribe]);

  useEffect(() => {
    return subscribe("error", (data: Record<string, unknown>) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      const msg = typeof data.message === "string" ? data.message : "Pipeline failure";
      toast.error(msg);
      setPipelineError(msg);
      setState("error");
    });
  }, [subscribe]);

  const handleSend = () => {
    if (!text.trim() || state === "streaming") return;
    setSteps([]);
    setCitations([]);
    setAnswer(null);
    setPipelineError(null);
    sessionIdRef.current = crypto.randomUUID();
    setState("streaming");
    send({
      query: text.trim(),
      kb_name: kbName,
      mode,
      retrieval_pipeline: retrieval,
      session_id: sessionIdRef.current,
    });
  };

  const handleReset = () => {
    setState("idle");
    setSteps([]);
    setAnswer(null);
    setCitations([]);
    setPipelineError(null);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => setDragging(false);

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!kbName) {
      toast.error("Select a Knowledge Base target first.");
      return;
    }
    const file = e.dataTransfer.files[0];
    if (file) await processFileUpload(file);
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) await processFileUpload(file);
  };

  const processFileUpload = async (file: File) => {
    const ext = file.name.split(".").pop()?.toLowerCase();
    const allowed = ["pdf", "txt", "md"];
    if (!allowed.includes(ext ?? "")) {
      toast.error("Supported formats: PDF, TXT, MD");
      return;
    }
    setUploadProgress(file.name);
    const result = await uploadDocument(file, kbName);
    if (result && result.task_id) {
      setPendingUploadName(file.name);
      setActiveUploadTaskId(result.task_id);
    } else {
      setUploadProgress(null);
      toast.error("Failed to upload document.");
    }
  };

  const filterTree = (node: IndexNode | null, query: string): IndexNode | null => {
    if (!node) return null;
    if (!query) return node;
    const matchesThis =
      node.title.toLowerCase().includes(query.toLowerCase()) ||
      node.summary.toLowerCase().includes(query.toLowerCase());
    const filteredChildren = node.children
      .map((child) => filterTree(child, query))
      .filter((child): child is IndexNode => child !== null);
    if (matchesThis || filteredChildren.length > 0) {
      return { ...node, children: filteredChildren };
    }
    return null;
  };

  const filteredTree = filterTree(indexTree, treeSearch);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-3 sm:-mx-5 md:-mx-6 lg:-mx-8 -my-3 sm:-my-5 md:-my-6 lg:-my-8 overflow-hidden bg-zinc-950 text-zinc-100 antialiased relative">
      {showLeftSidebar && (
        <SourcesSidebar
          documents={documents}
          loadingDocs={loadingDocs}
          selectedDocId={selectedDocId}
          onSelectDoc={setSelectedDocId}
          kbName={kbName}
          kbOptions={kbOptions}
          onKbChange={setKbName}
          uploadProgress={uploadProgress}
          dragging={dragging}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onFileChange={handleFileChange}
          fileInputRef={fileInputRef}
          solveStatus={solveStatus}
        />
      )}

      <main className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950 relative select-text">
        <SolveToolbar
          showLeftSidebar={showLeftSidebar}
          showRightSidebar={showRightSidebar}
          onToggleLeft={() => setShowLeftSidebar(!showLeftSidebar)}
          onToggleRight={() => setShowRightSidebar(!showRightSidebar)}
          onReset={handleReset}
          canReset={state !== "idle"}
        />

        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          <div className="max-w-3xl mx-auto space-y-6">
            {state === "idle" && (
              <SuggestedPrompts onSelectPrompt={setText} />
            )}

            {state === "idle" && (
              <SolveComposer
                text={text}
                onTextChange={setText}
                mode={mode}
                onModeChange={setMode}
                retrieval={retrieval}
                onRetrievalChange={setRetrieval}
                onSend={handleSend}
              />
            )}

            {state === "streaming" && (
              <StreamingPipeline
                steps={steps}
                expandedStepIndex={expandedStepIndex}
                onToggleStep={(i) =>
                  setExpandedStepIndex(expandedStepIndex === i ? null : i)
                }
              />
            )}

            {state === "error" && pipelineError && (
              <ErrorBanner message={pipelineError} onDismiss={handleReset} />
            )}

            {state === "complete" && answer && (
              <SynthesisResult
                answer={answer}
                citations={citations}
                onNewSession={handleReset}
              />
            )}
          </div>
        </div>
      </main>

      {showRightSidebar && (
        <PageIndexSidebar
          tree={indexTree}
          loadingTree={loadingTree}
          selectedDocId={selectedDocId}
          searchQuery={treeSearch}
          onSearchChange={setTreeSearch}
          filteredTree={filteredTree}
        />
      )}
    </div>
  );
}
