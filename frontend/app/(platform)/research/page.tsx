"use client";

import { useState, useEffect, useRef } from "react";
import { FileSearch, Loader2, Plus, Sparkles, CheckCircle2, XCircle, Clock, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { API_BASE_URL } from "@/lib/config";

const TOPICS = [
  "Explain quantum entanglement",
  "Summarize recent advances in LLMs",
  "Compare renewable energy sources",
];

type SubtopicStatus = "PENDING" | "RESEARCHING" | "COMPLETED" | "FAILED";

type Subtopic = {
  id: string;
  query: string;
  status: SubtopicStatus;
  notes: string;
};

type SessionData = {
  session_id: string;
  query: string;
  status: string;
  queue: Subtopic[];
  final_report: string | null;
};

const STATUS_ICON: Record<SubtopicStatus, React.ReactNode> = {
  PENDING: <Clock className="h-3.5 w-3.5 text-zinc-500" />,
  RESEARCHING: <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-400" />,
  COMPLETED: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
  FAILED: <XCircle className="h-3.5 w-3.5 text-red-400" />,
};

const STATUS_BADGE: Record<SubtopicStatus, "zinc" | "yellow" | "green" | "red"> = {
  PENDING: "zinc",
  RESEARCHING: "yellow",
  COMPLETED: "green",
  FAILED: "red",
};

export default function ResearchPage() {
  const [topic, setTopic] = useState("");
  const [kbName, setKbName] = useState("default");
  const [kbs, setKbs] = useState<{ name: string }[]>([]);
  const [running, setRunning] = useState(false);
  const [session, setSession] = useState<SessionData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load knowledge bases on mount
  useEffect(() => {
    fetch(`${API_BASE_URL}/knowledge/bases`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setKbs(data);
          setKbName(data[0].name);
        }
      })
      .catch(() => {});
  }, []);

  // Poll session status while research is running
  useEffect(() => {
    if (!session?.session_id || session.status === "COMPLETED") return;

    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/research/${session.session_id}/status`);
        if (!res.ok) return;
        const data: SessionData = await res.json();
        setSession(data);

        if (data.status === "COMPLETED" || data.status === "FAILED") {
          setRunning(false);
          if (pollRef.current) clearInterval(pollRef.current);
        }
      } catch {
        // Silently retry on next interval
      }
    }, 2000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [session?.session_id, session?.status]);

  const handleStart = async () => {
    if (!topic.trim()) return;
    setRunning(true);
    setError(null);
    setSession(null);

    try {
      const res = await fetch(`${API_BASE_URL}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: topic,
          kb_name: kbName,
          mode: "parallel",
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${res.status}`);
      }

      const data = await res.json();
      const sessionId = data.session_id || data;

      // Initial fetch for session data
      const statusRes = await fetch(`${API_BASE_URL}/research/${sessionId}/status`);
      if (statusRes.ok) {
        setSession(await statusRes.json());
      } else {
        setSession({
          session_id: sessionId,
          query: topic,
          status: "RESEARCHING",
          queue: [],
          final_report: null,
        });
      }
    } catch (e: any) {
      setError(e.message || "Failed to start research");
      setRunning(false);
    }
  };

  const completedCount = session?.queue.filter((s) => s.status === "COMPLETED").length ?? 0;
  const totalCount = session?.queue.length ?? 0;
  const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Deep Research
        </h1>
        <p className="text-sm text-zinc-500">
          Multi-phase research pipeline: Plan &rarr; Research &rarr; Report.
          Automatically breaks your topic into sub-questions and researches each
          in parallel (max 5 concurrent).
        </p>
      </div>

      {/* How it works */}
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { phase: "1. Plan", desc: "Decompose topic into sub-questions", active: running && !session?.queue.length },
          { phase: "2. Research", desc: "Investigate each sub-question", active: running && !!session?.queue.length && !session?.final_report },
          { phase: "3. Report", desc: "Synthesize findings into report", active: session?.status === "COMPLETED" },
        ].map((p) => (
          <div
            key={p.phase}
            className={`rounded-lg border p-3 transition-colors ${
              p.active
                ? "border-indigo-500/50 bg-indigo-950/20"
                : "border-zinc-800 bg-zinc-900/50"
            }`}
          >
            <p className={`text-xs font-semibold ${p.active ? "text-indigo-300" : "text-indigo-400"}`}>
              {p.phase}
            </p>
            <p className="mt-1 text-xs text-zinc-500">{p.desc}</p>
          </div>
        ))}
      </div>

      {/* Topic input */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="flex items-center gap-2 mb-3">
          <FileSearch className="h-4 w-4 text-zinc-500" />
          <span className="text-sm font-medium text-zinc-300">
            Start a research session
          </span>
        </div>

        {/* KB selector */}
        {kbs.length > 0 && (
          <div className="mb-3">
            <label className="text-xs text-zinc-500 mb-1 block">Knowledge Base</label>
            <select
              value={kbName}
              onChange={(e) => setKbName(e.target.value)}
              disabled={running}
              className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
            >
              {kbs.map((kb) => (
                <option key={kb.name} value={kb.name}>{kb.name}</option>
              ))}
            </select>
          </div>
        )}

        <div className="flex gap-2">
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleStart()}
            placeholder="What would you like to research?"
            disabled={running}
            className="flex-1 rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
          />
          <button
            onClick={handleStart}
            disabled={running || !topic.trim()}
            className="flex items-center gap-1.5 rounded-md bg-zinc-100 px-4 py-2 text-xs font-semibold text-zinc-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            {running ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5" />
                Start
              </>
            )}
          </button>
        </div>

        {/* Quick topics */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {TOPICS.map((t) => (
            <button
              key={t}
              onClick={() => setTopic(t)}
              disabled={running}
              className="flex items-center gap-1 rounded-full border border-zinc-800 bg-zinc-900/60 px-2.5 py-1 text-[11px] text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-300 disabled:opacity-40"
            >
              <Plus className="h-3 w-3" />
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="rounded-lg border border-red-900/50 bg-red-900/10 px-4 py-3 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {/* Empty state */}
      {!running && !session && !error && (
        <div className="rounded-lg border border-zinc-800/50 bg-zinc-900/20 p-8 text-center">
          <p className="text-sm text-zinc-600">
            No active research sessions. Start one above.
          </p>
        </div>
      )}

      {/* Research progress */}
      {session && session.queue.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-zinc-300">Subtopics</h3>
            <span className="text-xs text-zinc-500">
              {completedCount}/{totalCount} complete ({progressPct}%)
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>

          {/* Subtopic list */}
          <div className="space-y-1.5">
            {session.queue.map((st) => (
              <div
                key={st.id}
                className="flex items-start gap-2.5 rounded-lg border border-zinc-800/60 bg-zinc-900/30 px-3 py-2.5"
              >
                <div className="mt-0.5">{STATUS_ICON[st.status]}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm text-zinc-300 truncate">{st.query}</p>
                    <Badge variant={STATUS_BADGE[st.status]} className="text-[10px] shrink-0">
                      {st.status}
                    </Badge>
                  </div>
                  {st.status === "COMPLETED" && st.notes && (
                    <p className="mt-1.5 text-xs text-zinc-500 line-clamp-2">{st.notes.slice(0, 200)}...</p>
                  )}
                  {st.status === "FAILED" && st.notes && (
                    <p className="mt-1.5 text-xs text-red-400">{st.notes}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Final Report */}
      {session?.final_report && (
        <div className="rounded-lg border border-emerald-900/50 bg-emerald-900/5 p-5">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-semibold text-emerald-300">Research Report</h3>
          </div>
          <div className="prose prose-invert prose-sm max-w-none text-zinc-300 whitespace-pre-wrap">
            {session.final_report}
          </div>
        </div>
      )}
    </div>
  );
}
