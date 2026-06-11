"use client";

import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
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

  useEffect(() => { streamingAnswerRef.current = streamingAnswer; }, [streamingAnswer]);
  useEffect(() => { streamingStepsRef.current = streamingSteps; }, [streamingSteps]);
  const [activeAccordion, setActiveAccordion] = useState(true);
  const [expandedThoughtIndex, setExpandedThoughtIndex] = useState<string | null>(null);

  const [selectedKb, setSelectedKb] = useState<string>("");
  const [selectedNbId, setSelectedNbId] = useState<string | null>(null);
  const [nbRefreshKey, setNbRefreshKey] = useState(0);

  const [retrievalMode, setRetrievalMode] = useState<SolveQuery["retrieval_pipeline"]>("tree");
  const [solveMode, setSolveMode] = useState<SolveQuery["mode"]>("auto");

  const sessionIdRef = useRef<string>(crypto.randomUUID());
  const streamingAnswerRef = useRef("");
  const streamingStepsRef = useRef<Record<string, string>>({});

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
        (data as Record<string, unknown>).answer ?? streamingAnswerRef.current
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
          steps: streamingStepsRef.current,
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
  }, [subscribe]);

  useEffect(() => {
    return subscribe("error", (data) => {
      if (data.session_id && data.session_id !== sessionIdRef.current) return;
      setIsStreaming(false);
      toast.error(
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
    toast.success("Copied reply markdown to clipboard.");
  };

  const handleSaveMessageToNotebook = async (text: string) => {
    if (!selectedNbId) {
      toast.error(
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
      toast.success("Added chat response to Notebook.");
    } catch (err: unknown) {
      toast.error(
        err instanceof Error ? err.message : "Failed to append note."
      );
    }
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-3 sm:-mx-5 md:-mx-6 lg:-mx-8 -my-3 sm:-my-5 md:-my-6 lg:-my-8 overflow-hidden bg-zinc-950 text-zinc-100 antialiased relative">
      {showLeftSidebar && (
        <ChatSessionSidebar
          onKbChange={setSelectedKb}
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
        />
      )}
    </div>
  );
}
