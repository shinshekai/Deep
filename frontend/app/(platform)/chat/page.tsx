"use client";

import { useState, useRef, useEffect, type FormEvent } from "react";
import { Send, Trash2, Brain } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useWebSocket } from "@/providers/websocket-provider";
import type { SolveQuery } from "@/types/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export default function ChatPage() {
  const { solveStatus, send, subscribe } = useWebSocket();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Subscribe to streaming responses
  useEffect(() => {
    return subscribe("agent_step", (data) => {
      setStreamingContent((prev) => prev + (data.content as string) + "\n");
    });
  }, [subscribe]);

  useEffect(() => {
    return subscribe("complete", (data) => {
      const answer = (data as any).answer as string;
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant" as const,
          content: answer || streamingContent,
          timestamp: Date.now(),
        },
      ]);
      setStreamingContent("");
      setIsStreaming(false);
    });
  }, [subscribe]);

  useEffect(() => {
    return subscribe("error", (data) => {
      setIsStreaming(false);
      setStreamingContent((prev) => prev + `\n\nError: ${(data as any).message}`);
    });
  }, [subscribe]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);

    setIsStreaming(true);
    setStreamingContent("");

    const query: SolveQuery = {
      query: input.trim(),
      kb_name: "",
      mode: "auto",
      retrieval_pipeline: "tree",
    };
    send(query as unknown as Record<string, unknown>);
    setInput("");
  };

  const clearChat = () => {
    setMessages([]);
    setStreamingContent("");
    setIsStreaming(false);
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-zinc-400" />
          <h1 className="text-lg font-semibold">Chat</h1>
        </div>
        <div className="flex items-center gap-3">
          {messages.length > 0 && (
            <button
              onClick={clearChat}
              className="flex items-center gap-1 rounded px-2 py-1 text-xs text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Clear
            </button>
          )}
          <span
            className={`h-2 w-2 rounded-full ${solveStatus === "open" ? "bg-emerald-500" : "bg-zinc-600"}`}
          />
        </div>
      </div>

      {/* Message area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !streamingContent && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center space-y-3 max-w-md">
              <Brain className="mx-auto h-12 w-12 text-zinc-700" />
              <p className="text-lg font-medium text-zinc-400">
                Start a conversation
              </p>
              <p className="text-sm text-zinc-600">
                Ask questions about your documents. The multi-agent system will
                analyze, reason, and synthesize an answer.
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-3 ${msg.role === "user" ? "bg-indigo-600 text-white" : "bg-zinc-800 text-zinc-200"}`}
            >
              {msg.role === "user" ? (
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        ))}

        {streamingContent && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg bg-zinc-800 px-4 py-3 text-zinc-200">
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {streamingContent}
                </ReactMarkdown>
              </div>
              <span className="mt-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-zinc-800 p-4"
      >
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your documents..."
            disabled={isStreaming}
            className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900/80 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-zinc-100 px-4 py-2 text-sm font-semibold text-zinc-900 hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send className="h-4 w-4" />
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
