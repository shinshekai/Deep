"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { linkifyCitations } from "@/lib/markdown-citations";
import {
  FileSearch, Loader2, Sparkles, CheckCircle2,
  PanelLeft, PanelRight, Database, PlayCircle, BarChart3,
  Terminal, ShieldCheck, Timer, Cpu, Copy, RefreshCw, Layers
} from "lucide-react";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import { toast } from "sonner";

const TOPICS = [
  {
    title: "Quantum Entanglement",
    desc: "Explain non-locality, Einstein-Podolsky-Rosen paradox, and Bell test experiments.",
    query: "Explain quantum entanglement, non-locality, and EPR paradox with experimental proofs."
  },
  {
    title: "Large Language Models",
    desc: "Summarize recent advances in MoE, sliding window attention, and KV cache quantization.",
    query: "Summarize recent advances in LLM architectures (MoE, RoPE, KV Cache Quantization)."
  },
  {
    title: "Energy Storage Systems",
    desc: "Compare solid-state batteries, lithium-ion, and grid-scale thermal storage methods.",
    query: "Compare chemical, physical, and thermodynamic energy storage systems for smart grids."
  }
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

const AGENT_COLORS: Record<string, { text: string; bg: string; border: string; glow: string }> = {
  0: { text: "text-indigo-400", bg: "bg-indigo-950/15", border: "border-indigo-900/30", glow: "shadow-indigo-500/10" },
  1: { text: "text-purple-400", bg: "bg-purple-950/15", border: "border-purple-900/30", glow: "shadow-purple-500/10" },
  2: { text: "text-pink-400", bg: "bg-pink-950/15", border: "border-pink-900/30", glow: "shadow-pink-500/10" },
  3: { text: "text-amber-400", bg: "bg-amber-950/15", border: "border-amber-900/30", glow: "shadow-amber-500/10" },
  4: { text: "text-emerald-400", bg: "bg-emerald-950/15", border: "border-emerald-900/30", glow: "shadow-emerald-500/10" }
};

export default function ResearchPage() {
  const [topic, setTopic] = useState("");
  const [kbName, setKbName] = useState("default");
  const [kbs, setKbs] = useState<{ name: string }[]>([]);
  const [running, setRunning] = useState(false);
  const [session, setSession] = useState<SessionData | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Layout View Toggles
  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightSidebar, setShowRightSidebar] = useState(true);

  // Interactive UI states
  const [elapsedTime, setElapsedTime] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load knowledge bases on mount
  useEffect(() => {
    secureFetch(`${API_BASE_URL}/knowledge/bases`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setKbs(data);
          setKbName(data[0].name);
        }
      })
      .catch(() => {});
  }, []);

  // Timer controls
  useEffect(() => {
    if (running) {
      setElapsedTime(0);
      timerRef.current = setInterval(() => {
        setElapsedTime((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [running]);

  // Poll session status while research is running
  useEffect(() => {
    if (!session?.session_id || session.status === "COMPLETED") return;

    pollRef.current = setInterval(async () => {
      try {
        const res = await secureFetch(`${API_BASE_URL}/research/${session.session_id}`);
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
    setSession(null);
    setElapsedTime(0);

    try {
      const res = await secureFetch(`${API_BASE_URL}/research`, {
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
      const statusRes = await secureFetch(`${API_BASE_URL}/research/${sessionId}`);
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
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to start research";
      toast.error(msg);
      setRunning(false);
    }
  };

  const copyReport = (txt: string) => {
    navigator.clipboard.writeText(txt);
    toast.success("Copied final research report to clipboard.");
  };

  const completedCount = session?.queue.filter((s) => s.status === "COMPLETED").length ?? 0;
  const totalCount = session?.queue.length ?? 0;
  const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-3 sm:-mx-5 md:-mx-6 lg:-mx-8 -my-3 sm:-my-5 md:-my-6 lg:-my-8 overflow-hidden bg-zinc-950 text-zinc-100 antialiased relative">
      
      {/* ─── LEFT COLUMN: Scope Ingestion & Controls ─── */}
      {showLeftSidebar && (
        <aside className="w-80 shrink-0 border-r border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <Database className="h-4 w-4 text-indigo-400" />
              Research Parameters
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {/* KB Selection */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Target Knowledge Base
              </label>
              <select
                value={kbName}
                onChange={(e) => setKbName(e.target.value)}
                disabled={running}
                aria-label="Select target knowledge base"
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans disabled:opacity-50"
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

            {/* Pipeline Configuration Details */}
            <div className="rounded-xl border border-zinc-900 bg-zinc-950/30 p-3.5 space-y-3.5">
              <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono border-b border-zinc-900 pb-2">
                <Cpu className="h-3.5 w-3.5 text-indigo-400" />
                <span>Pipeline Engine</span>
              </div>
              <div className="space-y-2.5 font-mono text-[9px] text-zinc-500">
                <div className="flex justify-between items-center bg-zinc-950/40 p-2 border border-zinc-900 rounded">
                  <span>ROUTING MODE:</span>
                  <span className="font-bold text-indigo-400 uppercase">PARALLEL THREADS</span>
                </div>
                <div className="flex justify-between items-center bg-zinc-950/40 p-2 border border-zinc-900 rounded">
                  <span>CONCURRENT LIMIT:</span>
                  <span className="font-bold text-zinc-300">5 SUB-AGENTS</span>
                </div>
                <div className="flex justify-between items-center bg-zinc-950/40 p-2 border border-zinc-900 rounded">
                  <span>REASONING DEPTH:</span>
                  <span className="font-bold text-zinc-300">DEEP DUAL-LOOP</span>
                </div>
              </div>
            </div>

            {/* Suggested Search topics */}
            <div className="space-y-2.5">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Suggested Topics
              </label>
              <div className="space-y-2">
                {TOPICS.map((t) => (
                  <button
                    key={t.title}
                    onClick={() => setTopic(t.query)}
                    disabled={running}
                    aria-label={`Research topic: ${t.title}`}
                    className="w-full text-left rounded-xl border border-zinc-900/60 bg-zinc-950/20 p-3 hover:border-indigo-500/20 hover:bg-indigo-950/5 transition select-none disabled:opacity-40"
                  >
                    <div className="text-xs font-bold text-zinc-350 flex items-center gap-1">
                      <Sparkles className="h-3 w-3 text-indigo-400" />
                      {t.title}
                    </div>
                    <p className="text-[9px] text-zinc-400 mt-1 line-clamp-2 leading-relaxed">
                      {t.desc}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="p-4 border-t border-zinc-900 bg-zinc-950/40 text-[10px] text-zinc-500 font-mono flex items-center justify-between">
            <span className="flex items-center gap-1"><ShieldCheck className="h-3.5 w-3.5 text-emerald-500" /> offline ready</span>
            <span className="text-[9px] uppercase font-bold font-mono bg-zinc-900 px-1 py-0.5 rounded text-zinc-400">DeepTutor</span>
          </div>
        </aside>
      )}

      {/* ─── CENTER COLUMN: Active Workspace ─── */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950 relative select-text">
        
        {/* Top Control Bar */}
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-900 bg-zinc-950/40 px-4 select-none">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowLeftSidebar(!showLeftSidebar)}
              className={`p-1.5 rounded-lg border transition ${
                showLeftSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
              title="Toggle Parameters Sidebar"
              aria-label="Toggle parameters sidebar"
              aria-expanded={showLeftSidebar}
            >
              <PanelLeft className="h-4 w-4" />
            </button>
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <span className="text-xs font-semibold text-zinc-250 font-mono">Deep Research Lab</span>
          </div>

          <div className="flex items-center gap-2">
            {session && (
              <button
                onClick={() => {
                  setSession(null);
                  setRunning(false);
                  setTopic("");
                }}
                aria-label="Reset research session"
                className="flex items-center gap-1 rounded bg-zinc-900 hover:bg-zinc-800/80 px-2 py-1 text-xs text-zinc-400 transition"
              >
                Reset Session
              </button>
            )}
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <button
              onClick={() => setShowRightSidebar(!showRightSidebar)}
              className={`p-1.5 rounded-lg border transition ${
                showRightSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
              title="Toggle Telemetry Sidebar"
              aria-label="Toggle telemetry sidebar"
              aria-expanded={showRightSidebar}
            >
              <PanelRight className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Dynamic Inner Panel Viewport */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
          <div className="max-w-3xl mx-auto space-y-6">
            
            {/* 1. Welcome Composer (Idle screen) */}
            {!running && !session && (
              <div className="space-y-6">
                <div className="rounded-xl border border-zinc-900/60 bg-zinc-950 p-6 space-y-4 select-none text-center max-w-xl mx-auto py-12">
                  <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-650/10 border border-indigo-500/20 text-indigo-400 shadow-inner mb-2 animate-pulse">
                    <FileSearch className="h-6 w-6" />
                  </div>
                  <h2 className="text-2xl font-extrabold tracking-tight bg-gradient-to-r from-zinc-100 via-indigo-200 to-zinc-400 bg-clip-text text-transparent">
                    Autonomous Deep Research
                  </h2>
                  <p className="text-xs text-zinc-500 leading-relaxed max-w-sm mx-auto">
                    Type a complex topic prompt. Our multi-agent orchestrator will decompose your prompt into subtopics, research each concurrently, and write an academic-grade executive summary.
                  </p>
                </div>

                <div className="rounded-2xl border border-zinc-900 bg-zinc-950 p-4 space-y-4 shadow-xl select-none max-w-2xl mx-auto">
                  <textarea
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Enter what you would like to research in depth..."
                    rows={4}
                    aria-label="Enter research topic"
                    className="w-full rounded-xl border border-zinc-900 bg-zinc-950/20 px-3 py-2.5 text-xs md:text-sm text-zinc-100 placeholder-zinc-700 focus:outline-none focus:border-indigo-650 font-sans leading-relaxed resize-none"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleStart();
                      }
                    }}
                  />
                  <div className="flex justify-end pt-1 border-t border-zinc-900/60">
                    <button
                      onClick={handleStart}
                      disabled={!topic.trim()}
                      aria-label="Start research pipeline"
                      className="flex items-center gap-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white font-bold text-xs px-4.5 py-2.5 transition cursor-pointer shadow-md shadow-indigo-600/10"
                    >
                      <PlayCircle className="h-4 w-4" />
                      <span>Start Research Pipeline</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 2. Pipeline Execution Dashboard */}
            {session && (
              <div className="space-y-6">
                
                {/* Active topic card banner */}
                <div className="rounded-xl border border-zinc-900 bg-zinc-900/40 p-4 select-text">
                  <div className="flex items-start gap-3">
                    <div className="h-8 w-8 rounded-lg bg-indigo-650/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
                      <FileSearch className="h-4.5 w-4.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[10px] font-mono text-zinc-400 font-extrabold uppercase">
                        ACTIVE TOPIC SEARCH
                      </div>
                      <h2 className="text-sm font-bold text-zinc-200 mt-0.5 select-text">
                        {session.query}
                      </h2>
                    </div>
                  </div>
                </div>

                {/* STAGE 1: Decomposed hierarchical query tree */}
                {session.queue.length > 0 && !session.final_report && (
                  <div className="space-y-3 animate-slide-in">
                    <div className="flex items-center gap-2 border-b border-zinc-900 pb-2">
                      <Layers className="h-4 w-4 text-indigo-400" />
                      <span className="text-[10px] uppercase font-extrabold font-mono text-zinc-400 tracking-wider">
                        Stage 1 &mdash; Query Topic Decomposition
                      </span>
                    </div>

                    <div className="rounded-xl border border-zinc-900 bg-zinc-950 p-4 font-mono text-[10px] space-y-2 select-none">
                      <div className="text-zinc-300 font-bold flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
                        Root: {session.query.substring(0, 50)}...
                      </div>
                      <div className="space-y-1.5 pl-4 border-l border-zinc-900">
                        {session.queue.map((st, i) => (
                          <div key={st.id} className="flex items-start gap-2 text-zinc-500">
                            <span className="text-zinc-500 font-extrabold">├─ sub_q[{i+1}]:</span>
                            <span className="text-zinc-400">{st.query}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* STAGE 2: Live concurrent agent research cards */}
                {session.queue.length > 0 && !session.final_report && (
                  <div className="space-y-3.5 animate-slide-in">
                    <div className="flex items-center gap-2 border-b border-zinc-900 pb-2">
                      <RefreshCw className="h-4 w-4 text-indigo-400 animate-spin" />
                      <span className="text-[10px] uppercase font-extrabold font-mono text-zinc-400 tracking-wider">
                        Stage 2 &mdash; Parallel Investigations ({completedCount}/{totalCount})
                      </span>
                    </div>

                    {/* Concurrency Cards grid */}
                    <div className="grid gap-3 sm:grid-cols-2">
                      {session.queue.map((st, idx) => {
                        const am = AGENT_COLORS[idx % 5];
                        const isCompleted = st.status === "COMPLETED";
                        const isResearching = st.status === "RESEARCHING";
                        const isFailed = st.status === "FAILED";

                        return (
                          <div
                            key={st.id}
                            className={`rounded-xl border p-4 space-y-2.5 transition-all duration-300 relative shadow-inner ${
                              isResearching
                                ? `border-indigo-500/40 bg-indigo-950/5 ${am.glow}`
                                : isFailed
                                  ? "border-red-900/50 bg-red-950/5"
                                  : "border-zinc-900 bg-zinc-950/20"
                            }`}
                          >
                            <div className="flex items-center justify-between border-b border-zinc-900/60 pb-1.5">
                              <span className="text-[9px] font-mono text-zinc-600 font-extrabold uppercase">
                                AGENT #{idx+1} TARGET
                              </span>
                              <div className="flex items-center gap-1.5">
                                {isResearching && (
                                  <span className="relative flex h-1.5 w-1.5 shrink-0">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-amber-500" />
                                  </span>
                                )}
                                <span className={`text-[9px] font-mono font-bold uppercase ${
                                  isCompleted ? "text-emerald-400" : isResearching ? "text-amber-400" : isFailed ? "text-red-400" : "text-zinc-400"
                                }`}>
                                  {st.status}
                                </span>
                              </div>
                            </div>

                            <p className="text-[11px] font-semibold text-zinc-200 line-clamp-2 leading-relaxed h-8">
                              {st.query}
                            </p>

                            {/* Agent notes preview */}
                            <div className="border-t border-zinc-900/40 pt-2 text-[10px] text-zinc-500 leading-relaxed font-sans">
                              {isCompleted && st.notes ? (
                                  <p className="line-clamp-2 italic">
                                    {st.notes}
                                  </p>
                              ) : isResearching ? (
                                <p className="animate-pulse text-zinc-400 flex items-center gap-1">
                                  <Loader2 className="h-3 w-3 animate-spin" /> Ingesting sources & extracting notes...
                                </p>
                              ) : isFailed ? (
                                <p className="text-red-400/80">{st.notes || "Parsing failure."}</p>
                              ) : (
                                <p className="text-zinc-500 font-mono uppercase">Queued in priority buffer</p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* STAGE 3: Completed synthesis report workspace */}
                {session.final_report && (
                  <div className="space-y-4 animate-slide-in">
                    
                    {/* Response sheet */}
                    <div className="rounded-xl border border-zinc-900 bg-zinc-950 p-6 space-y-5 shadow-2xl select-text">
                      
                      <div className="flex items-center justify-between border-b border-zinc-900 pb-3 select-none">
                        <span className="text-xs uppercase font-extrabold text-indigo-400 tracking-wider font-mono flex items-center gap-1.5">
                          <CheckCircle2 className="h-4.5 w-4.5 text-emerald-400" />
                          Stage 3 &mdash; Synthesis Report
                        </span>
                        <button
                          onClick={() => copyReport(session.final_report || "")}
                          aria-label="Copy report to clipboard"
                          className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-300 transition"
                        >
                          <Copy className="h-3.5 w-3.5" />
                          <span>Copy Report</span>
                        </button>
                      </div>

                      {/* Render markdown body */}
                      <div className="prose prose-invert prose-xs md:prose-sm max-w-none prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-zinc-900 prose-code:text-indigo-400 select-text leading-relaxed font-sans">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {linkifyCitations(session.final_report)}
                        </ReactMarkdown>
                      </div>

                      {/* Diagnostic details */}
                      <div className="flex justify-between items-center text-[9px] font-mono text-zinc-500 pt-2.5 border-t border-zinc-900/60 select-none">
                        <span>Research Session: {session.session_id.substring(0, 16)}</span>
                        <span>Completed: {completedCount} subtopics researched in {elapsedTime}s</span>
                      </div>
                    </div>
                  </div>
                )}

              </div>
            )}
          </div>
        </div>
      </main>

      {/* ─── RIGHT COLUMN: Observability Telemetry ─── */}
      {showRightSidebar && (
        <aside className="w-80 shrink-0 border-l border-zinc-900 bg-zinc-950/40 flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <BarChart3 className="h-4 w-4 text-indigo-400" />
              Observability Rail
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            
            {/* Timeline Progress Bar dial */}
            {session && (
              <div className="rounded-xl border border-zinc-900 bg-zinc-950/30 p-4 space-y-3.5">
                <div className="flex items-center justify-between text-[9px] text-zinc-400 font-mono uppercase">
                  <span>Research Progress</span>
                  <span className="font-bold text-zinc-300">{progressPct}%</span>
                </div>
                <div className="relative h-2 w-full rounded-full bg-zinc-900 overflow-hidden">
                  <div 
                    className="absolute h-full rounded-full bg-indigo-500 transition-all duration-500"
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-[9px] text-zinc-500 font-mono">
                  <span>COMPLETED: {completedCount}</span>
                  <span>TOTAL: {totalCount}</span>
                </div>
              </div>
            )}

            {/* Research Telemetry */}
            <div className="rounded-xl border border-zinc-900 bg-zinc-950/30 p-4 space-y-3.5">
              <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono border-b border-zinc-900 pb-2">
                <Terminal className="h-3.5 w-3.5 text-indigo-400" />
                <span>Execution Logs</span>
              </div>

              <div className="space-y-2.5 max-h-[220px] overflow-y-auto pr-1">
                {session ? (
                  <>
                    <div className="text-[10px] text-zinc-400 leading-normal border-l-2 border-indigo-800 pl-2">
                      <div className="font-bold font-mono text-zinc-450 flex items-center justify-between">
                        <span>INIT_RESEARCH</span>
                        <span className="text-[9px] font-normal font-mono">0.0s</span>
                      </div>
                      <p className="mt-0.5">Started autonomous research session successfully.</p>
                    </div>
                    {session.queue.map((st, i) => {
                      const isComp = st.status === "COMPLETED";
                      const isFailed = st.status === "FAILED";
                      const isRes = st.status === "RESEARCHING";
                      return (
                        <div key={st.id} className={`text-[10px] text-zinc-400 leading-normal border-l-2 pl-2 ${
                          isComp ? "border-emerald-800" : isFailed ? "border-red-800" : isRes ? "border-amber-800" : "border-zinc-800"
                        }`}>
                          <div className="font-bold font-mono text-zinc-450 flex items-center justify-between">
                            <span>SUB_Q[{i+1}]</span>
                            <span className={`text-[8px] px-1 rounded uppercase font-mono ${
                              isComp ? "bg-emerald-950/40 text-emerald-400" : isFailed ? "bg-red-950/40 text-red-400" : isRes ? "bg-amber-950/40 text-amber-400 animate-pulse" : "bg-zinc-900 text-zinc-400"
                            }`}>{st.status}</span>
                          </div>
                          <p className="mt-0.5 truncate max-w-[190px]">{st.query}</p>
                        </div>
                      );
                    })}
                    {session.final_report && (
                      <div className="text-[10px] text-zinc-400 leading-normal border-l-2 border-emerald-800 pl-2 bg-emerald-950/5">
                        <div className="font-bold font-mono text-emerald-400">REPORT_COMPLETE</div>
                        <p className="mt-0.5 text-emerald-300/80">Executive final report compiled and formatted.</p>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-6 text-zinc-500 text-xs font-mono">
                    Session inactive. Waiting for prompt ingress.
                  </div>
                )}
              </div>
            </div>

            {/* Performance Timers dial */}
            <div className="rounded-xl border border-zinc-900 bg-zinc-950/30 p-4 space-y-3.5">
              <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono border-b border-zinc-900 pb-2">
                <Timer className="h-3.5 w-3.5 text-indigo-400" />
                <span>Timer stats</span>
              </div>
              <div className="grid grid-cols-2 gap-3 font-mono">
                <div className="bg-zinc-950/50 border border-zinc-900 rounded p-2.5 text-center">
                  <div className="text-[9px] uppercase font-semibold text-zinc-500">ELAPSED</div>
                  <div className="text-xs font-bold text-zinc-200 mt-1">{elapsedTime}s</div>
                </div>
                <div className="bg-zinc-950/50 border border-zinc-900 rounded p-2.5 text-center">
                  <div className="text-[9px] uppercase font-semibold text-zinc-500">AVG TIMER</div>
                  <div className="text-xs font-bold text-zinc-200 mt-1">
                    {completedCount > 0 ? (elapsedTime / completedCount).toFixed(1) + "s" : "0.0s"}
                  </div>
                </div>
              </div>
            </div>

          </div>
        </aside>
      )}

    </div>
  );
}
