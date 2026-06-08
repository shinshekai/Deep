"use client";

import { useState, useRef, useEffect } from "react";
import { AlertCircle, CheckCircle2, X } from "lucide-react";
import { useWebSocket } from "@/providers/websocket-provider";
import type { SolveQuery, Citation } from "@/types/api";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import type { Message } from "@/components/chat/types";
import { ChatHeader } from "@/components/chat/ChatHeader";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatSessionSidebar } from "@/components/chat/ChatSessionSidebar";
import { ChatInferenceDisplay } from "@/components/chat/ChatInferenceDisplay";

const STORAGE_KEY = "udip_chat_history";

export default function ChatPage() {
  const { solveStatus, send, subscribe } = useWebSocket();

  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightSidebar, setShowRightSidebar] = useState(true);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingSteps, setStreamingSteps] = useState<Record<string, string>>({});
  const [streamingAgent, setStreamingAgent] = useState<string | null>(null);
  const [streamingAnswer, setStreamingAnswer] = useState("");
  const [activeAccordion, setActiveAccordion] = useState(true);
  const [expandedThoughtIndex, setExpandedThoughtIndex] = useState<string | null>(null);

  const [selectedKb, setSelectedKb] = useState<string>("");
  const [selectedNbId, setSelectedNbId] = useState<string | null>(null);
  const [nbRefreshKey, setNbRefreshKey] = useState(0);

  const [retrievalMode, setRetrievalMode] = useState<SolveQuery["retrieval_pipeline"]>("tree");
  const [solveMode, setSolveMode] = useState<SolveQuery["mode"]>("auto");

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const sessionIdRef = useRef<string>(crypto.randomUUID());

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) setMessages(JSON.parse(saved));
      } catch {}
    }
  }, []);

  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
      } catch {}
    }, 500);
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [messages]);

  useEffect(() => {
    return subscribe("agent_step", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      const agent = data.agent as string;
      const delta = (data.delta as string) || (data.content as string) || "";
      setStreamingAgent(agent);
      if (agent === "format") {
        setStreamingAnswer((prev) => prev + delta);
      } else {
        setStreamingSteps((prev) => ({
          ...prev,
          [agent]: (prev[agent] || "") + delta,
        }));
      }
    });
  }, [subscribe]);

  useEffect(() => {
    return subscribe("complete", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      const completeAnswer = String(
        (data as Record<string, unknown>).answer ?? streamingAnswer
      );
      const meta =
        ((data as Record<string, unknown>).metadata as
          | Record<string, unknown>
          | undefined) ?? {};
      const citationsRaw = (data as Record<string, unknown>).citations;
      const citationsList = Array.isArray(citationsRaw) ? citationsRaw : [];
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: completeAnswer,
          timestamp: Date.now(),
          steps: streamingSteps,
          citations: citationsList as unknown as Citation[],
          modelUsed: meta.model_used as string | undefined,
          complexityScore: meta.complexity_score as number | undefined,
          targetTier: meta.target_tier as string | undefined,
          elapsedSeconds: meta.elapsed_seconds as number | undefined,
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
      setErrorMsg(
        String(
          (data as Record<string, unknown>).message ??
            "AI Synthesizer pipeline failed."
        )
      );
    });
  }, [subscribe]);

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
    send({
      ...query,
      session_id: sessionIdRef.current,
    } as unknown as Record<string, unknown>);
    setInput("");
  };

  const onSubmitForm = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend(input);
  };

  const clearChat = () => {
    setMessages([]);
    setStreamingAnswer("");
    setStreamingSteps({});
    setStreamingAgent(null);
    setIsStreaming(false);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSuccessMsg("Copied reply markdown to clipboard.");
    setTimeout(() => setSuccessMsg(null), 2500);
  };

  const handleSaveMessageToNotebook = async (text: string) => {
    if (!selectedNbId) {
      setErrorMsg(
        "Please select or construct a Notebook in the right panel first."
      );
      return;
    }
    try {
      const res = await secureFetch(
        `${API_BASE_URL}/notebooks/${selectedNbId}/notes`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text, source: "chat" }),
        }
      );
      if (!res.ok) throw new Error("Save note failed.");
      setNbRefreshKey((k) => k + 1);
      setSuccessMsg("Added chat response to Notebook.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error ? err.message : "Failed to append note."
      );
    }
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-3 sm:-mx-5 md:-mx-6 lg:-mx-8 -my-3 sm:-my-5 md:-my-6 lg:-my-8 overflow-hidden bg-zinc-950 text-zinc-100 antialiased relative">
      {showLeftSidebar && (
        <ChatSessionSidebar
          onKbChange={setSelectedKb}
          setErrorMsg={setErrorMsg}
        />
      )}

      <main className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950 relative select-text">
        <ChatHeader
          showLeftSidebar={showLeftSidebar}
          onToggleLeft={() => setShowLeftSidebar(!showLeftSidebar)}
          showRightSidebar={showRightSidebar}
          onToggleRight={() => setShowRightSidebar(!showRightSidebar)}
          hasMessages={messages.length > 0}
          onClearChat={clearChat}
        />
        <ChatMessageList
          messages={messages}
          isStreaming={isStreaming}
          streamingSteps={streamingSteps}
          streamingAgent={streamingAgent}
          streamingAnswer={streamingAnswer}
          activeAccordion={activeAccordion}
          onToggleAccordion={() => setActiveAccordion(!activeAccordion)}
          expandedThoughtIndex={expandedThoughtIndex}
          onToggleThought={(id) =>
            setExpandedThoughtIndex(
              expandedThoughtIndex === id ? null : id
            )
          }
          onSend={handleSend}
          onSaveToNotebook={handleSaveMessageToNotebook}
          onCopyToClipboard={copyToClipboard}
        />
        <ChatInput
          input={input}
          onInputChange={setInput}
          isStreaming={isStreaming}
          onSubmit={onSubmitForm}
          retrievalMode={retrievalMode}
          onRetrievalModeChange={setRetrievalMode}
          solveMode={solveMode}
          onSolveModeChange={setSolveMode}
          solveStatus={solveStatus}
        />
      </main>

      {showRightSidebar && (
        <ChatInferenceDisplay
          selectedNbId={selectedNbId}
          onNotebookChange={setSelectedNbId}
          refreshKey={nbRefreshKey}
          setErrorMsg={setErrorMsg}
          setSuccessMsg={setSuccessMsg}
        />
      )}

      <div
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 select-none pointer-events-none max-w-sm"
        role="status"
        aria-live="polite"
      >
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
            <button
              onClick={() => setErrorMsg(null)}
              className="ml-auto text-red-500 hover:text-red-400"
              aria-label="Dismiss error"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
