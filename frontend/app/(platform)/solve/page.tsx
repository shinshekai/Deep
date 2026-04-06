"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useWebSocket } from "@/providers/websocket-provider";
import { SolveInput } from "@/components/solve/solve-input";
import { AgentStepDisplay } from "@/components/solve/agent-step-display";
import { CitationList } from "@/components/solve/citation-list";
import { Badge } from "@/components/ui/badge";
import type {
  SolveQuery,
  AgentStepFrame,
  Citation,
  CompleteFrame,
  ErrorFrame,
} from "@/types/api";

type SolveState = "idle" | "streaming" | "complete" | "error";

export default function SolvePage() {
  const { solveStatus, send, subscribe } = useWebSocket();
  const [state, setState] = useState<SolveState>("idle");
  const [steps, setSteps] = useState<AgentStepFrame[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [answer, setAnswer] = useState<CompleteFrame | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const sessionIdRef = useRef<string>(crypto.randomUUID());

  // Subscribe to agent steps
  useEffect(() => {
    return subscribe("agent_step", (data) => {
      setSteps((prev) => [
        ...prev,
        { ...data, timestamp: data.timestamp ?? Date.now() / 1000 } as AgentStepFrame,
      ]);
    });
  }, [subscribe]);

  // Subscribe to citations
  useEffect(() => {
    return subscribe("citation", (data) => {
      if (data.citation) {
        setCitations((prev) => [...prev, data.citation as Citation]);
      }
    });
  }, [subscribe]);

  // Subscribe to completion
  useEffect(() => {
    return subscribe("complete", (data) => {
      setAnswer(data as CompleteFrame);
      setState("complete");
    });
  }, [subscribe]);

  // Subscribe to errors
  useEffect(() => {
    return subscribe("error", (data) => {
      setErrorMsg((data as ErrorFrame).message ?? "Unknown error");
      setState("error");
    });
  }, [subscribe]);

  const handleSend = useCallback(
    (query: SolveQuery) => {
      setSteps([]);
      setCitations([]);
      setAnswer(null);
      setErrorMsg(null);
      sessionIdRef.current = crypto.randomUUID();
      setState("streaming");
      send({ ...query, session_id: sessionIdRef.current });
    },
    [send]
  );

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Smart Solve</h1>
          <p className="text-sm text-zinc-500">
            Multi-agent analysis and synthesis. Query your knowledge base with
            hierarchical retrieval and agent reasoning.
          </p>
        </div>
        <Badge variant={solveStatus === "open" ? "green" : "zinc"} dot>
          Solve: {solveStatus}
        </Badge>
      </div>

      {/* Input */}
      <SolveInput onSend={handleSend} isStreaming={state === "streaming"} />

      {/* Streaming: show agent steps */}
      {state === "streaming" && (
        <AgentStepDisplay steps={steps} />
      )}

      {/* Error state */}
      {state === "error" && (
        <div className="rounded-lg border border-red-900/50 bg-red-900/10 p-4">
          <p className="text-sm font-semibold text-red-400">Error</p>
          <p className="mt-1 text-sm text-zinc-400">{errorMsg}</p>
          <button
            onClick={() => setState("idle")}
            className="mt-3 rounded bg-red-900/30 px-3 py-1 text-xs text-red-300 hover:bg-red-900/40"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Complete: show answer + citations */}
      {state === "complete" && answer && (
        <div className="space-y-4">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
            <h2 className="mb-3 text-sm font-semibold text-zinc-300">Answer</h2>
            <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800 prose-code:text-amber-300 prose-a:text-indigo-400">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {answer.answer}
              </ReactMarkdown>
            </div>
          </div>

          {answer.citations.length > 0 && (
            <CitationList citations={answer.citations} />
          )}

          {answer.solve_dir && (
            <p className="text-xs text-zinc-600 font-mono">
              Session artifacts: {answer.solve_dir}
            </p>
          )}

          <button
            onClick={() => {
              setState("idle");
              setSteps([]);
              setCitations([]);
              setAnswer(null);
            }}
            className="mt-2 rounded bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100"
          >
            New Query
          </button>
        </div>
      )}
    </div>
  );
}
