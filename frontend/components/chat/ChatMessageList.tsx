"use client";

import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { linkifyCitations } from "@/lib/markdown-citations";
import { useChatAutoScroll } from "@/hooks/use-chat-auto-scroll";
import { useSmoothStream } from "@/hooks/use-smooth-stream";
import {
  Brain,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  CheckSquare,
  FileText,
  Copy,
  Save,
  User,
  Loader2,
  BookOpen,
  Sparkles,
  Layers,
} from "lucide-react";
import type { Message } from "./types";

interface ChatMessageListProps {
  messages: Message[];
  isStreaming: boolean;
  streamingSteps: Record<string, string>;
  streamingAgent: string | null;
  streamingAnswer: string;
  activeAccordion: boolean;
  onToggleAccordion: () => void;
  expandedThoughtIndex: string | null;
  onToggleThought: (id: string) => void;
  onSend: (text: string) => void;
  onSaveToNotebook: (text: string) => void;
  onCopyToClipboard: (text: string) => void;
}

const suggestionCards = [
  {
    title: "Summarize Workspace",
    desc: "Distill the core conceptual claims and indexing highlights.",
    icon: BookOpen,
    prompt:
      "Generate a comprehensive summary of all materials loaded in our active Knowledge Base workspace.",
  },
  {
    title: "Synthesize Gaps",
    desc: "Uncover missing links or contradictory statements.",
    icon: Sparkles,
    prompt:
      "Analyze the active indexed documents and synthesize any potential research gaps or unproven arguments.",
  },
  {
    title: "Compare Architectures",
    desc: "Assess differing formulas, metrics, or methods.",
    icon: Layers,
    prompt:
      "Find and compare the core methodologies or technical architectures discussed in these documents.",
  },
];

function MessageItem({
  msg,
  expandedThoughtIndex,
  onToggleThought,
  onSaveToNotebook,
  onCopyToClipboard,
}: {
  msg: Message;
  expandedThoughtIndex: string | null;
  onToggleThought: (id: string) => void;
  onSaveToNotebook: (text: string) => void;
  onCopyToClipboard: (text: string) => void;
}) {
  const isUser = msg.role === "user";
  return (
    <div
      className={`flex gap-3 md:gap-4 max-w-3xl mx-auto ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
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
            <p className="text-xs md:text-sm whitespace-pre-wrap leading-relaxed">
              {msg.content}
            </p>
          ) : (
            <div className="space-y-4">
              {msg.steps && Object.keys(msg.steps).length > 0 && (
                <div className="border border-zinc-900/60 rounded-lg overflow-hidden bg-zinc-950/30">
                  <button
                    type="button"
                    onClick={() => onToggleThought(msg.id)}
                    className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-mono text-zinc-500 hover:text-zinc-300 transition focus:outline-none"
                    aria-label="Toggle multi-agent steps"
                    aria-expanded={expandedThoughtIndex === msg.id}
                  >
                    <span className="flex items-center gap-1.5 uppercase font-bold tracking-wider">
                      <CheckSquare className="h-3.5 w-3.5 text-emerald-500" />
                      Multi-Agent Steps (
                      {Object.keys(msg.steps).length})
                    </span>
                    {expandedThoughtIndex === msg.id ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                  </button>
                  {expandedThoughtIndex === msg.id && (
                    <div className="px-3 pb-3 pt-0 border-t border-zinc-900/40 max-h-60 overflow-y-auto space-y-2.5">
                      {Object.entries(msg.steps).map(([agent, txt]) => (
                        <div
                          key={agent}
                          className="text-[10px] font-mono border-l-2 border-zinc-800 pl-2 leading-relaxed"
                        >
                          <span className="font-extrabold uppercase text-indigo-400">
                            {agent}:
                          </span>
                          <p className="text-zinc-450 mt-0.5 whitespace-pre-wrap">
                            {txt}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="prose prose-invert prose-xs md:prose-sm max-w-none prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-zinc-900 prose-code:text-indigo-400 prose-a:text-indigo-400 select-text leading-relaxed">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {linkifyCitations(msg.content)}
                </ReactMarkdown>
              </div>

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

        {!isUser && (
          <div className="flex items-center gap-3 px-1 text-[10px] text-zinc-500 select-none">
            <button
              onClick={() => onCopyToClipboard(msg.content)}
              className="flex items-center gap-1 hover:text-zinc-300 transition"
              title="Copy text"
              aria-label="Copy response"
            >
              <Copy className="h-3 w-3" />
              <span>Copy</span>
            </button>
            <span className="h-3 w-[1px] bg-zinc-850" />
            <button
              onClick={() => onSaveToNotebook(msg.content)}
              className="flex items-center gap-1 hover:text-zinc-300 transition text-indigo-400/80 hover:text-indigo-300"
              title="Save response as note in active Notebook"
              aria-label="Save to notebook"
            >
              <Save className="h-3 w-3" />
              <span>Save to Notebook</span>
            </button>

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
}

export function ChatMessageList({
  messages,
  isStreaming,
  streamingSteps,
  streamingAgent,
  streamingAnswer,
  activeAccordion,
  onToggleAccordion,
  expandedThoughtIndex,
  onToggleThought,
  onSend,
  onSaveToNotebook,
  onCopyToClipboard,
}: ChatMessageListProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 120,
    overscan: 5,
  });

  useChatAutoScroll(parentRef, {
    isStreaming,
    itemCount: messages.length,
    streamChunk: streamingAnswer,
  });

  const smoothAnswer = useSmoothStream(streamingAnswer, isStreaming);

  return (
    <div className="flex-1 p-4 md:p-6 space-y-6">
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
              Ask questions about your loaded documents. The multi-agent
              pipeline will analyze references, reason recursively, and write
              answers into notes.
            </p>
          </div>

          <div
            className="grid gap-3 sm:grid-cols-3"
            role="group"
            aria-label="Suggested prompts"
          >
            {suggestionCards.map((card) => {
              const Icon = card.icon;
              return (
                <button
                  key={card.title}
                  type="button"
                  onClick={() => onSend(card.prompt)}
                  className="group flex flex-col justify-between rounded-xl border border-zinc-900 bg-zinc-950/40 p-4 transition text-left cursor-pointer hover:border-indigo-500/20 hover:bg-indigo-950/5 hover:-translate-y-0.5 focus-visible:outline-none focus-visible:border-indigo-500 focus-visible:ring-2 focus-visible:ring-indigo-500/40"
                >
                  <Icon className="h-4.5 w-4.5 text-zinc-500 group-hover:text-indigo-400 transition" />
                  <div className="mt-4">
                    <div className="text-xs font-bold text-zinc-350">
                      {card.title}
                    </div>
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

      {messages.length > 0 && (
        <div
          ref={parentRef}
          className="max-w-3xl mx-auto overflow-y-auto"
          style={{ height: "calc(100vh - 200px)", contain: "strict" }}
        >
          <div
            style={{ height: virtualizer.getTotalSize(), position: "relative" }}
          >
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const msg = messages[virtualRow.index];
              return (
                <div
                  key={msg.id}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  <MessageItem
                    msg={msg}
                    expandedThoughtIndex={expandedThoughtIndex}
                    onToggleThought={onToggleThought}
                    onSaveToNotebook={onSaveToNotebook}
                    onCopyToClipboard={onCopyToClipboard}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {isStreaming && (
        <div className="flex gap-3 md:gap-4 max-w-3xl mx-auto justify-start animate-pulse">
          <div className="h-7 w-7 rounded-lg bg-indigo-650/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0 select-none animate-spin">
            <RefreshCw className="h-4.5 w-4.5" />
          </div>
          <div className="flex-1 flex flex-col gap-2 min-w-0 max-w-[85%]">
            <div className="rounded-2xl border border-indigo-900/35 bg-indigo-950/5 px-4.5 py-3.5 space-y-4">
              <div className="border border-indigo-900/20 rounded-lg overflow-hidden bg-zinc-950/40">
                <button
                  type="button"
                  onClick={onToggleAccordion}
                  className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-mono text-indigo-400 focus:outline-none"
                  aria-label="Toggle solving pipeline details"
                  aria-expanded={activeAccordion}
                >
                  <span className="flex items-center gap-1.5 uppercase font-bold tracking-wider">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Solving Pipeline Live...
                  </span>
                  {activeAccordion ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )}
                </button>
                {activeAccordion && (
                  <div className="px-3 pb-3 pt-0 border-t border-indigo-900/10 max-h-60 overflow-y-auto space-y-2.5">
                    {Object.entries(streamingSteps).map(([agent, txt]) => (
                      <div
                        key={agent}
                        className="text-[10px] font-mono border-l-2 border-indigo-850 pl-2 leading-relaxed"
                      >
                        <span className="font-extrabold uppercase text-indigo-300">
                          {agent}:
                        </span>
                        <p className="text-zinc-500 mt-0.5 whitespace-pre-wrap">
                          {txt}
                        </p>
                      </div>
                    ))}
                    {streamingAgent && streamingAgent !== "format" && (
                      <div className="text-[10px] font-mono border-l-2 border-amber-800 pl-2 leading-relaxed animate-pulse">
                        <span className="font-extrabold uppercase text-amber-500">
                          {streamingAgent} thinking:
                        </span>
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500 ml-1.5" />
                      </div>
                    )}
                  </div>
                )}
              </div>

              {streamingAnswer && (
                <div className="prose prose-invert prose-xs md:prose-sm max-w-none prose-code:text-indigo-400 select-text leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {linkifyCitations(smoothAnswer)}
                  </ReactMarkdown>
                  <span className="inline-block h-2 w-2 rounded-full bg-indigo-500 animate-ping ml-1" />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
