"use client";

import { useState, useEffect } from "react";
import { BookOpen, MessageSquare, Target, ClipboardList, Loader2, Send, ChevronRight, PlayCircle, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function GuidedLearningPage() {
  const [kbName, setKbName] = useState("default");
  const [kbs, setKbs] = useState<{ name: string }[]>([]);
  const [topic, setTopic] = useState("");
  
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

  useEffect(() => {
    fetch("/api/v1/knowledge/bases")
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setKbs(data);
          setKbName(data[0].name);
        }
      })
      .catch((err) => console.error("Failed to load KBs", err));
  }, []);

  const startSession = async () => {
    if (!topic.trim()) return;
    setIsStarting(true);
    setHtmlContent("");
    setChatHistory([]);
    setSummary(null);

    try {
      const res = await fetch("/api/v1/learning/start", {
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
    } finally {
      setIsStarting(false);
    }
  };

  const loadPage = async (sid: string, pIndex: number) => {
    setIsLoadingPage(true);
    setHtmlContent("");
    setChatHistory([]); // Clear chat for new point
    
    try {
      const res = await fetch(`/api/v1/learning/${sid}/page`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ point_index: pIndex }),
      });
      const data = await res.json();
      setHtmlContent(data.html || "<p>Failed to generate content.</p>");
    } catch (e) {
      console.error(e);
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
      const res = await fetch(`/api/v1/learning/${sessionId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ point_index: currentPointIndex, message: userMsg }),
      });
      const data = await res.json();
      setChatHistory((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (e) {
      console.error(e);
    } finally {
      setIsChatting(false);
    }
  };

  const endSession = async () => {
    if (!sessionId) return;
    setIsEnding(true);
    try {
      const res = await fetch(`/api/v1/learning/${sessionId}/end`, {
        method: "POST"
      });
      const data = await res.json();
      setSummary(data);
      setCurrentPointIndex(-1); // Switch view to summary
    } catch (e) {
      console.error(e);
    } finally {
      setIsEnding(false);
    }
  };

  // If no session is active, show the setup screen
  if (!sessionId) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-100px)] p-6">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            <div className="inline-flex items-center justify-center h-16 w-16 rounded-full bg-indigo-500/10 mb-4">
              <Target className="h-8 w-8 text-indigo-400" />
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-100">Guided Learning</h1>
            <p className="text-zinc-500 mt-2 text-sm leading-relaxed">
              An AI tutor will segment your topic into manageable steps, generate interactive lessons, and answer your questions contextually.
            </p>
          </div>

          <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 shadow-xl">
            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-zinc-400 mb-1.5 block">Knowledge Base</label>
                <select
                  value={kbName}
                  onChange={(e) => setKbName(e.target.value)}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-300 focus:outline-none focus:border-indigo-500 transition-colors"
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
                <label className="text-xs font-medium text-zinc-400 mb-1.5 block">What do you want to learn?</label>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. Transformers architecture, Quantum mechanics..."
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-300 focus:outline-none focus:border-indigo-500 placeholder:text-zinc-600 transition-colors"
                />
              </div>

              <button
                onClick={startSession}
                disabled={isStarting || !topic.trim()}
                className="w-full mt-4 flex items-center justify-center gap-2 rounded-md bg-indigo-500 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-500/20"
              >
                {isStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
                {isStarting ? "Locating Knowledge..." : "Start Learning Path"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Active Session View
  return (
    <div className="flex h-[calc(100vh-64px)] max-h-[calc(100vh-64px)] overflow-hidden">
      
      {/* Sidebar: Learning Path */}
      <div className="w-80 border-r border-zinc-800 bg-zinc-950/50 flex flex-col">
        <div className="p-4 border-b border-zinc-800">
          <Badge variant="outline" className="mb-2 bg-indigo-500/10 text-indigo-400 border-indigo-500/20">Active Session</Badge>
          <h2 className="text-sm font-semibold text-zinc-200 line-clamp-2">{topic}</h2>
        </div>
        
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider px-2 pt-2 pb-1">Learning Path</p>
          {points.map((pt, idx) => (
            <button
              key={idx}
              onClick={() => handlePointSelect(idx)}
              className={`w-full text-left p-3 rounded-lg text-sm transition-all flex items-start gap-3 ${
                currentPointIndex === idx 
                  ? "bg-zinc-800 border-l-2 border-indigo-500 text-zinc-200" 
                  : "bg-transparent text-zinc-400 hover:bg-zinc-900"
              }`}
            >
              <span className={`flex-shrink-0 flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold ${
                currentPointIndex === idx ? "bg-indigo-500 text-white" : "bg-zinc-800 text-zinc-500"
              }`}>
                {idx + 1}
              </span>
              <span className="line-clamp-2 leading-relaxed">{pt}</span>
            </button>
          ))}
        </div>

        <div className="p-4 border-t border-zinc-800">
          <button 
            onClick={endSession}
            disabled={isEnding || summary !== null}
            className="w-full flex items-center justify-center gap-2 rounded-md bg-zinc-800 px-4 py-2 text-xs font-semibold text-zinc-200 transition-colors hover:bg-zinc-700 disabled:opacity-50"
          >
            {isEnding ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4 text-green-400" />}
            Complete Session
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col bg-zinc-900/20 relative">
        {summary ? (
          <div className="flex-1 overflow-y-auto p-10 flex justify-center items-start">
            <div className="max-w-2xl w-full bg-zinc-900/80 border border-zinc-800 rounded-xl p-8 shadow-2xl">
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-green-500/10 rounded-full">
                  <ClipboardList className="h-6 w-6 text-green-400" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-zinc-100">Session Summary</h2>
                  <p className="text-sm text-zinc-400">Great job completing the path!</p>
                </div>
              </div>
              <div className="prose prose-invert max-w-none text-sm text-zinc-300">
                <p>{summary.summary}</p>
                {summary.next_steps && summary.next_steps.length > 0 && (
                  <>
                    <h4 className="text-zinc-200 mt-6 mb-2 font-semibold">Recommended Next Steps:</h4>
                    <ul className="space-y-1">
                      {summary.next_steps.map((step: string, i: number) => (
                        <li key={i} className="flex items-start gap-2">
                          <ChevronRight className="h-4 w-4 mt-0.5 text-indigo-400 shrink-0" />
                          <span>{step}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
              <button 
                onClick={() => window.location.reload()}
                className="mt-8 px-4 py-2 bg-zinc-100 text-zinc-900 text-sm font-semibold rounded hover:bg-white transition-colors"
              >
                Start New Topic
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* HTML Render Area */}
            <div className="flex-1 overflow-y-auto p-8 prose prose-invert prose-indigo max-w-none">
              {isLoadingPage ? (
                <div className="h-full flex flex-col items-center justify-center text-zinc-500 gap-4">
                  <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
                  <p className="text-sm">Generating interactive lesson...</p>
                </div>
              ) : htmlContent ? (
                <div dangerouslySetInnerHTML={{ __html: htmlContent }} className="learning-content pb-20" />
              ) : (
                <div className="h-full flex items-center justify-center text-zinc-500">
                  <p>Select a point from the learning path.</p>
                </div>
              )}
            </div>

            {/* Chat Widget (Fixed at bottom right) */}
            {currentPointIndex >= 0 && (
              <div className="absolute bottom-6 right-6 w-96 rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl flex flex-col overflow-hidden transition-all h-[400px]">
                <div className="flex items-center gap-2 p-3 bg-zinc-900 border-b border-zinc-800">
                  <MessageSquare className="h-4 w-4 text-indigo-400" />
                  <span className="text-xs font-semibold text-zinc-200">Tutor Chat</span>
                </div>
                
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {chatHistory.length === 0 ? (
                    <div className="text-center mt-10">
                      <p className="text-xs text-zinc-500">Ask questions about this specific topic.</p>
                    </div>
                  ) : (
                    chatHistory.map((msg, i) => (
                      <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                          msg.role === "user" 
                            ? "bg-indigo-600 text-white" 
                            : "bg-zinc-800 text-zinc-300"
                        }`}>
                          {msg.content}
                        </div>
                      </div>
                    ))
                  )}
                  {isChatting && (
                    <div className="flex justify-start">
                      <div className="max-w-[85%] rounded-lg px-3 py-2 bg-zinc-800 text-zinc-400">
                        <Loader2 className="h-4 w-4 animate-spin" />
                      </div>
                    </div>
                  )}
                </div>

                <form onSubmit={sendChat} className="p-3 border-t border-zinc-800 bg-zinc-900 flex gap-2">
                  <input
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask a question..."
                    className="flex-1 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500"
                  />
                  <button 
                    type="submit" 
                    disabled={isChatting || !chatInput.trim()}
                    className="p-1.5 rounded-md bg-indigo-500 text-white disabled:opacity-50 transition-colors hover:bg-indigo-600"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                </form>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
