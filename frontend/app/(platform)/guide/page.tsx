"use client";

import { useState, useEffect, useRef } from "react";
import { 
  BookOpen, MessageSquare, Target, ClipboardList, Loader2, Send, 
  ChevronRight, ChevronDown, PlayCircle, CheckCircle2, PanelLeft, PanelRight, 
  HelpCircle, Sparkles, Database, Plus, Trash, Clock, X, Badge, AlertCircle 
} from "lucide-react";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import DOMPurify from "dompurify";

const SUGGESTIONS = [
  "Transformers attention mechanism details",
  "Principles of Quantum Cryptography",
  "Asymmetric KV Cache Quantization models"
];

export default function GuidedLearningPage() {
  const [kbName, setKbName] = useState("default");
  const [kbs, setKbs] = useState<{ name: string }[]>([]);
  const [topic, setTopic] = useState("");
  
  // Layout views
  const [showLeftSidebar, setShowLeftSidebar] = useState(true);
  const [showRightSidebar, setShowRightSidebar] = useState(true);

  // Session State
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [points, setPoints] = useState<string[]>([]);
  const [currentPointIndex, setCurrentPointIndex] = useState<number>(-1);
  const [isStarting, setIsStarting] = useState(false);
  const [isLoadingPage, setIsLoadingPage] = useState(false);
  
  // Interactive Content State
  const [htmlContent, setHtmlContent] = useState<string>("");
  
  // Chat State
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<{role: string, content: string}[]>([]);
  const [isChatting, setIsChatting] = useState(false);

  // Summary State
  const [summary, setSummary] = useState<any>(null);
  const [isEnding, setIsEnding] = useState(false);

  // Error State
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    secureFetch(`${API_BASE_URL}/knowledge/bases`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setKbs(data);
          setKbName(data[0].name);
        }
      })
      .catch((err) => {
        console.error("Failed to load KBs", err);
        setErrorMsg("Failed to load knowledge bases. Check your connection and try again.");
      });
  }, []);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, isChatting]);

  const startSession = async () => {
    if (!topic.trim()) return;
    setIsStarting(true);
    setHtmlContent("");
    setChatHistory([]);
    setSummary(null);

    try {
      const res = await secureFetch(`${API_BASE_URL}/learning/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kb_name: kbName, topic }),
      });
      const data = await res.json();
      if (data.session_id) {
        setSessionId(data.session_id);
        setPoints(data.points || []);
        setCurrentPointIndex(0);
        await loadPage(data.session_id, 0);
      }
    } catch (e) {
      console.error(e);
      setErrorMsg("Failed to start learning session. The AI tutor may be temporarily unavailable.");
    } finally {
      setIsStarting(false);
    }
  };

  const loadPage = async (sid: string, pIndex: number) => {
    setIsLoadingPage(true);
    setHtmlContent("");
    setChatHistory([]); // Clear chat for new point
    
    try {
      const res = await secureFetch(`${API_BASE_URL}/learning/${sid}/page`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ point_index: pIndex }),
      });
      const data = await res.json();
      setHtmlContent(data.html || "<p>Failed to generate content.</p>");
    } catch (e) {
      console.error(e);
      setErrorMsg("Failed to load lesson content. Please try again.");
    } finally {
      setIsLoadingPage(false);
    }
  };

  const handlePointSelect = (idx: number) => {
    if (idx === currentPointIndex) return;
    setCurrentPointIndex(idx);
    if (sessionId) {
      loadPage(sessionId, idx);
    }
  };

  const sendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !sessionId || currentPointIndex < 0) return;

    const userMsg = chatInput.trim();
    setChatInput("");
    setChatHistory((prev) => [...prev, { role: "user", content: userMsg }]);
    setIsChatting(true);

    try {
      const res = await secureFetch(`${API_BASE_URL}/learning/${sessionId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ point_index: currentPointIndex, message: userMsg }),
      });
      const data = await res.json();
      setChatHistory((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (e) {
      console.error(e);
      setErrorMsg("Failed to send message. Please try again.");
    } finally {
      setIsChatting(false);
    }
  };

  const endSession = async () => {
    if (!sessionId) return;
    setIsEnding(true);
    try {
      const res = await secureFetch(`${API_BASE_URL}/learning/${sessionId}/end`, {
        method: "POST"
      });
      const data = await res.json();
      setSummary(data);
      setCurrentPointIndex(-1); // Switch view to summary
    } catch (e) {
      console.error(e);
      setErrorMsg("Failed to end session. Your progress has been saved.");
    } finally {
      setIsEnding(false);
    }
  };

  // 1. Setup Screen (If no session is active)
  if (!sessionId) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] p-4 md:p-8">
        {errorMsg && (
          <div className="mb-4 w-full max-w-md flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-xs text-red-300" role="alert">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="flex-1">{errorMsg}</span>
            <button onClick={() => setErrorMsg(null)} className="shrink-0 p-0.5 hover:text-red-200" aria-label="Dismiss error">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
        <div className="max-w-md w-full space-y-8 select-none">
          <div className="text-center space-y-3">
            <div className="inline-flex items-center justify-center h-14 w-14 rounded-2xl bg-indigo-650/10 border border-indigo-500/20 text-indigo-400 shadow-inner animate-pulse">
              <Target className="h-6 w-6" />
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-zinc-100 via-indigo-200 to-zinc-400 bg-clip-text text-transparent">
              Guided AI Tutor
            </h1>
            <p className="text-zinc-500 text-xs md:text-sm leading-relaxed max-w-sm mx-auto">
              Our deliberate AI-tutor segments your syllabus into modular milestones, builds interactive chapters, and stands ready to dialogue contextually.
            </p>
          </div>

          <div className="rounded-2xl border border-zinc-900 bg-zinc-950 p-6 shadow-xl space-y-4">
            <div className="space-y-4">
              <div>
                <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono mb-1.5 block">
                  Knowledge Base Scope
                </label>
                <select
                  value={kbName}
                  onChange={(e) => setKbName(e.target.value)}
                  aria-label="Select knowledge base scope"
                  className="w-full rounded-lg border border-zinc-850 bg-zinc-900 px-3 py-2.5 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
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

              <div>
                <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono mb-1.5 block">
                  What do you want to learn?
                </label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Multi-Head Attention, Bell Inequality proofs..."
                  aria-label="Learning topic"
                  className="w-full rounded-lg border border-zinc-850 bg-zinc-900 px-3 py-2.5 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans"
                />
              </div>

              <button
                onClick={startSession}
                disabled={isStarting || !topic.trim()}
                aria-label="Start guided learning session"
                className="w-full mt-4 flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-indigo-600/10 cursor-pointer"
              >
                {isStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                {isStarting ? "Assembling syllabus..." : "Construct Interactive Path"}
              </button>
            </div>

            {/* Quick topics select */}
            <div className="pt-2 border-t border-zinc-900/60 flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setTopic(s)}
                  aria-label={`Set topic: ${s}`}
                  className="rounded-full border border-zinc-900 bg-zinc-950 px-2.5 py-1 text-[9px] font-mono text-zinc-500 hover:text-zinc-350 transition cursor-pointer"
                >
                  + {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 2. Active Session Workspace (Side-by-side dashboard)
  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-3 sm:-mx-5 md:-mx-6 lg:-mx-8 -my-3 sm:-my-5 md:-my-6 lg:-my-8 overflow-hidden bg-zinc-950 text-zinc-100 antialiased relative">
      
      {/* Error banner */}
      {errorMsg && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/90 px-4 py-2.5 text-xs text-red-300 shadow-xl backdrop-blur-sm max-w-lg" role="alert">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="flex-1">{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="shrink-0 p-0.5 hover:text-red-200" aria-label="Dismiss error">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* ─── LEFT COLUMN: Learning roadmap tree ─── */}
      {showLeftSidebar && (
        <aside className="w-80 shrink-0 border-r border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <BookOpen className="h-4 w-4 text-indigo-400 animate-pulse" />
              Syllabus Roadmap
            </span>
          </div>
          
          <div className="flex-1 overflow-y-auto p-3 space-y-1.5" role="listbox" aria-label="Syllabus roadmap">
            {points.map((pt, idx) => {
              const isActive = currentPointIndex === idx;
              const isPassed = idx < currentPointIndex;

              return (
                <button
                  key={idx}
                  onClick={() => handlePointSelect(idx)}
                  aria-label={`Go to lesson ${idx + 1}: ${pt}`}
                  aria-current={isActive ? "true" : undefined}
                  role="option"
                  aria-selected={isActive}
                  className={`w-full text-left p-3 rounded-xl border transition-all flex items-start gap-2.5 cursor-pointer ${
                    isActive 
                      ? "bg-indigo-950/20 border-indigo-500/30 text-indigo-200" 
                      : "border-zinc-900/60 bg-zinc-950/30 text-zinc-450 hover:bg-zinc-900/40 hover:text-zinc-300"
                  }`}
                >
                  <span className={`shrink-0 flex items-center justify-center h-5 w-5 rounded-lg text-[9px] font-extrabold font-mono border ${
                    isActive 
                      ? "bg-indigo-600 border-indigo-500 text-white" 
                      : isPassed
                        ? "bg-emerald-950/40 border-emerald-900 text-emerald-400"
                        : "bg-zinc-900 border-zinc-800 text-zinc-500"
                  }`}>
                    {isPassed ? "✓" : idx + 1}
                  </span>
                  <span className="text-xs font-semibold leading-relaxed line-clamp-2">{pt}</span>
                </button>
              );
            })}
          </div>

          <div className="p-4 border-t border-zinc-900 bg-zinc-950/40 select-none">
            <button 
              onClick={endSession}
              disabled={isEnding || summary !== null}
              aria-label="Complete learning session"
              className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-700 hover:text-zinc-300 px-4 py-2 text-xs font-bold text-zinc-400 transition disabled:opacity-40"
            >
              {isEnding ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
              Complete Session
            </button>
          </div>
        </aside>
      )}

      {/* ─── CENTER COLUMN: Interactive Reading Workspace ─── */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950 relative select-text">
        {/* Solve Control Toolbar */}
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-zinc-900 bg-zinc-950/40 px-4 select-none">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowLeftSidebar(!showLeftSidebar)}
              aria-label="Toggle syllabus sidebar"
              aria-expanded={showLeftSidebar}
              className={`p-1.5 rounded-lg border transition ${
                showLeftSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <PanelLeft className="h-4 w-4" />
            </button>
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <span className="text-xs font-semibold text-zinc-250 font-mono">Interactive Chapter Reader</span>
          </div>

          <div className="flex items-center gap-2">
            {sessionId && (
              <button
                onClick={() => {
                  setSessionId(null);
                  setPoints([]);
                  setCurrentPointIndex(-1);
                  setHtmlContent("");
                  setChatHistory([]);
                  setSummary(null);
                }}
                aria-label="Exit learning session"
                className="flex items-center gap-1 rounded bg-zinc-900 hover:bg-zinc-800/80 px-2 py-1 text-xs text-zinc-400 transition"
              >
                Exit Session
              </button>
            )}
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <button
              onClick={() => setShowRightSidebar(!showRightSidebar)}
              aria-label="Toggle tutor chat sidebar"
              aria-expanded={showRightSidebar}
              className={`p-1.5 rounded-lg border transition ${
                showRightSidebar ? "bg-zinc-900 border-zinc-800 text-zinc-200" : "bg-zinc-950 border-zinc-900 text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <PanelRight className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Primary lesson reader viewport */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 select-text bg-zinc-950">
          <div className="max-w-2xl mx-auto py-4">
            {summary ? (
              <div className="rounded-xl border border-zinc-900 bg-zinc-950 p-6 space-y-6 shadow-2xl animate-slide-in">
                <div className="flex items-center gap-3 border-b border-zinc-900 pb-4">
                  <div className="p-3 bg-emerald-950/40 rounded-xl border border-emerald-900/30 text-emerald-400 shrink-0">
                    <ClipboardList className="h-6 w-6" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-zinc-250 font-sans">Session Complete Summary</h2>
                    <p className="text-[10px] text-zinc-500 font-mono">CONGRATULATIONS ON FINISHING THE ROADMAP</p>
                  </div>
                </div>

                <div className="prose prose-invert prose-sm max-w-none text-zinc-350 leading-relaxed font-sans select-text">
                  <p className="whitespace-pre-wrap">{summary.summary}</p>
                  
                  {summary.next_steps && summary.next_steps.length > 0 && (
                    <div className="mt-6 border-t border-zinc-900 pt-4 space-y-2.5">
                      <h4 className="text-xs uppercase font-extrabold text-indigo-400 font-mono tracking-wider">
                        Recommended Next Milestones
                      </h4>
                      <ul className="space-y-2">
                        {summary.next_steps.map((step: string, i: number) => (
                          <li key={i} className="flex items-start gap-2.5 text-zinc-400 text-xs">
                            <ChevronRight className="h-4 w-4 mt-0.5 text-indigo-400 shrink-0" />
                            <span>{step}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <button 
                  onClick={() => window.location.reload()}
                  className="rounded-lg bg-zinc-100 text-zinc-950 text-xs font-bold px-4 py-2 hover:bg-white transition"
                >
                  Start New Session
                </button>
              </div>
            ) : (
              <div className="rounded-xl border border-zinc-900 bg-zinc-950 shadow-sm p-6 select-text min-h-[400px]">
                {isLoadingPage ? (
                  <div className="h-80 flex flex-col items-center justify-center text-zinc-400 gap-3 select-none">
                    <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
                    <p className="text-[10px] uppercase font-bold font-mono tracking-wider">
                      Generating Interactive Chapter...
                    </p>
                  </div>
                ) : htmlContent ? (
                  <div 
                    dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(htmlContent) }} 
                    className="learning-content pb-10 select-text prose prose-invert prose-xs md:prose-sm max-w-none prose-pre:bg-zinc-950 prose-pre:border prose-pre:border-zinc-900 prose-code:text-indigo-400 leading-relaxed font-sans" 
                  />
                ) : (
                  <div className="h-80 flex items-center justify-center text-zinc-500 text-xs select-none font-mono uppercase">
                    Select a syllabus checkpoint from the left panel
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* ─── RIGHT COLUMN: Integrated Tutor Chat dialog timeline ─── */}
      {showRightSidebar && (
        <aside className="w-80 shrink-0 border-l border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <MessageSquare className="h-4 w-4 text-indigo-400" />
              Tutor Consultation
            </span>
          </div>

          {/* Conversation speech bubble thread */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 select-text">
            {currentPointIndex < 0 ? (
              <div className="text-center py-12 text-zinc-500 text-xs font-mono uppercase">
                Active study point required for chat
              </div>
            ) : chatHistory.length === 0 ? (
              <div className="text-center py-16 space-y-2 text-zinc-600 select-none">
                <Sparkles className="h-6 w-6 text-zinc-700 mx-auto mb-1 animate-pulse" />
                <p className="text-xs font-bold uppercase tracking-wider font-mono">Tutor ready</p>
                <p className="text-[10px] text-zinc-500 font-sans max-w-[180px] mx-auto leading-normal">
                  Ask details, explain complex claims, or query concepts about this chapter.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {chatHistory.map((msg, i) => {
                  const isUser = msg.role === "user";
                  return (
                    <div 
                      key={i} 
                      className={`flex gap-2.5 max-w-[85%] ${isUser ? "ml-auto justify-end" : "justify-start"}`}
                    >
                      <div className={`rounded-2xl px-3.5 py-2.5 text-xs shadow-inner select-text leading-relaxed ${
                        isUser 
                          ? "bg-indigo-600/20 border border-indigo-500/30 text-zinc-150" 
                          : "bg-zinc-900/40 border border-zinc-900/80 text-zinc-300"
                      }`}>
                        {msg.content}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            
            {isChatting && (
              <div className="flex justify-start max-w-[85%]">
                <div className="rounded-2xl px-3.5 py-2.5 bg-zinc-900/40 border border-zinc-900 text-zinc-400">
                  <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Consultation Chat input form */}
          {currentPointIndex >= 0 && (
            <form onSubmit={sendChat} className="p-3 border-t border-zinc-900 bg-zinc-950/40 flex items-center gap-2 select-none">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Ask your AI tutor..."
                disabled={isChatting}
                aria-label="Chat message input"
                className="flex-1 rounded-xl border border-zinc-900 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none focus:border-indigo-650"
              />
              <button 
                type="submit" 
                disabled={isChatting || !chatInput.trim()}
                aria-label="Send chat message"
                className={`p-2 rounded-xl transition ${
                  isChatting || !chatInput.trim()
                    ? "bg-zinc-900 text-zinc-500"
                    : "bg-indigo-650 hover:bg-indigo-500 text-white"
                }`}
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </form>
          )}

        </aside>
      )}

    </div>
  );
}
