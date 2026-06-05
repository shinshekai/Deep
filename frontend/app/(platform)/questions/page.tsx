"use client";

import { useState, useEffect } from "react";
import { 
  FileQuestion, GraduationCap, ListChecks, Loader2, BookOpen, 
  ChevronDown, ChevronUp, PanelLeft, Database, Sparkles, CheckCircle2, 
  X, HelpCircle, Layers, Award, Info
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { API_BASE_URL, secureFetch } from "@/lib/config";

const QUESTION_TYPES = [
  { value: "mcq", label: "Multiple Choice" },
  { value: "short", label: "Short Answer" },
  { value: "essay", label: "Essay" },
  { value: "mimic", label: "Exam Mimicry" },
];

const DIFFICULTIES = [
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
];

export default function QuestionsPage() {
  const [kbName, setKbName] = useState("default");
  const [kbs, setKbs] = useState<{ name: string }[]>([]);
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [type, setType] = useState("mcq");
  const [difficulty, setDifficulty] = useState("medium");
  const [isGenerating, setIsGenerating] = useState(false);
  const [questions, setQuestions] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  // For exam mimicry
  const [referenceExam, setReferenceExam] = useState("");

  // Layout states
  const [showLeftSidebar, setShowLeftSidebar] = useState(true);

  useEffect(() => {
    secureFetch(`${API_BASE_URL}/knowledge/bases`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setKbs(data);
          setKbName(data[0].name);
        }
      })
      .catch((err) => console.error("Failed to load KBs", err));
  }, []);

  const handleGenerate = async () => {
    if (!topic.trim()) {
      setError("Please enter a topic first.");
      return;
    }

    setIsGenerating(true);
    setError(null);
    setQuestions([]);

    try {
      const res = await secureFetch(`${API_BASE_URL}/questions/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          kb_name: kbName,
          topic: topic,
          count: count,
          difficulty: difficulty,
          question_type: type,
          reference_exam: type === "mimic" ? referenceExam : undefined,
        }),
      });

      if (!res.ok) {
        throw new Error("Failed to generate practice set");
      }

      const data = await res.json();
      setQuestions(data.questions || []);
    } catch (err: any) {
      setError(err.message || "Failed to generate questions");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-3.5rem)] -mx-3 sm:-mx-5 md:-mx-6 lg:-mx-8 -my-3 sm:-my-5 md:-my-6 lg:-my-8 overflow-hidden bg-zinc-950 text-zinc-100 antialiased relative">
      
      {/* ─── LEFT COLUMN: Configuration Sidebar ─── */}
      {showLeftSidebar && (
        <aside className="w-80 shrink-0 border-r border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
          <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
            <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
              <GraduationCap className="h-4 w-4 text-indigo-400" />
              Syllabus Config
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-5">
            {/* Knowledge Base */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Target Knowledge Base
              </label>
              <select
                value={kbName}
                onChange={(e) => setKbName(e.target.value)}
                disabled={isGenerating}
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

            {/* Topic Input */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Topic / Concept Focus
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                disabled={isGenerating}
                placeholder="e.g. Backpropagation, Multi-head attention"
                className="w-full rounded-lg border border-zinc-850 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans"
              />
            </div>

            {/* Question Type selection grid */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Question Style
              </label>
              <div className="grid grid-cols-2 gap-2">
                {QUESTION_TYPES.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => setType(t.value)}
                    disabled={isGenerating}
                    className={`flex items-center gap-1.5 rounded-lg border p-2 text-[10px] font-semibold transition cursor-pointer select-none ${
                      type === t.value
                        ? "border-indigo-500/30 bg-indigo-950/20 text-indigo-300"
                        : "border-zinc-900 bg-zinc-950/40 text-zinc-500 hover:bg-zinc-900/40 hover:text-zinc-350"
                    }`}
                  >
                    {t.value === "mimic" ? (
                      <Award className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <FileQuestion className="h-3.5 w-3.5 shrink-0" />
                    )}
                    <span className="truncate">{t.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Exam reference textarea for mimicry */}
            {type === "mimic" && (
              <div className="space-y-2 animate-slide-in">
                <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                  Reference Exam Template
                </label>
                <textarea
                  value={referenceExam}
                  onChange={(e) => setReferenceExam(e.target.value)}
                  disabled={isGenerating}
                  placeholder="Paste past exam questions or template instructions here to mimic style..."
                  rows={3}
                  className="w-full rounded-lg border border-zinc-850 bg-zinc-900 p-2.5 text-xs text-zinc-250 placeholder-zinc-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none font-sans"
                />
              </div>
            )}

            {/* Difficulty selecting buttons */}
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Difficulty Level
              </label>
              <div className="flex gap-1.5">
                {DIFFICULTIES.map((d) => (
                  <button
                    key={d.value}
                    onClick={() => setDifficulty(d.value)}
                    disabled={isGenerating}
                    className={`flex-1 rounded-lg px-2.5 py-1.5 text-[10px] font-bold border transition cursor-pointer select-none ${
                      difficulty === d.value
                        ? "bg-zinc-100 text-zinc-950 border-zinc-100 font-semibold"
                        : "border-zinc-900 bg-zinc-950/40 text-zinc-500 hover:bg-zinc-900"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Count slider */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[10px] font-mono text-zinc-400">
                <span>QUESTION COUNT</span>
                <span className="font-bold text-zinc-300">{count}</span>
              </div>
              <input
                type="range"
                min={1}
                max={20}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                disabled={isGenerating}
                aria-label="Number of questions"
                className="w-full accent-indigo-500 cursor-pointer disabled:opacity-40"
              />
            </div>
          </div>

          <div className="p-4 border-t border-zinc-900 bg-zinc-950/40 select-none">
            <button
              onClick={handleGenerate}
              disabled={isGenerating || !topic.trim()}
              className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg shadow-indigo-600/10 cursor-pointer"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Compiling Practice Set...</span>
                </>
              ) : (
                <>
                  <ListChecks className="h-4 w-4" />
                  <span>Generate Questions</span>
                </>
              )}
            </button>
          </div>
        </aside>
      )}

      {/* ─── CENTER COLUMN: Generated Exam Workspace ─── */}
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
              aria-expanded={showLeftSidebar}
            >
              <PanelLeft className="h-4 w-4" />
            </button>
            <div className="h-4 w-[1px] bg-zinc-800 mx-1" />
            <span className="text-xs font-semibold text-zinc-250 font-mono">Question Studio</span>
          </div>

          <div className="flex items-center gap-2">
            {questions.length > 0 && (
              <button
                onClick={() => setQuestions([])}
                className="flex items-center gap-1.5 rounded-lg border border-zinc-900 hover:border-zinc-850 hover:bg-zinc-900/35 px-2.5 py-1 text-xs text-zinc-500 hover:text-zinc-300 transition"
              >
                Reset Studio
              </button>
            )}
          </div>
        </header>

        {/* Scrollable Main Exam viewport */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6 select-text bg-zinc-950">
          <div className="max-w-2xl mx-auto space-y-5 py-4">
            
            {/* If no questions yet: Welcome screen */}
            {questions.length === 0 && (
              <div className="rounded-xl border border-zinc-900/60 bg-zinc-950 p-6 space-y-4 select-none text-center max-w-md mx-auto py-12">
                <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-650/10 border border-indigo-500/20 text-indigo-400 shadow-inner mb-2 animate-pulse">
                  <GraduationCap className="h-6 w-6" />
                </div>
                <h2 className="text-2xl font-extrabold tracking-tight bg-gradient-to-r from-zinc-100 via-indigo-200 to-zinc-400 bg-clip-text text-transparent">
                  Interactive Practice Studio
                </h2>
                <p className="text-xs text-zinc-500 leading-relaxed max-w-xs mx-auto">
                  Type a topic and select options in the left panel. Our synthesis engine will extract concepts directly from your documents and assemble adaptive test questions contextually.
                </p>
              </div>
            )}

            {/* Generated Question Paper lists */}
            {questions.length > 0 && (
              <div className="space-y-4 animate-slide-in">
                <div className="flex items-center gap-2 border-b border-zinc-900 pb-2 select-none">
                  <Sparkles className="h-4 w-4 text-indigo-400 animate-pulse" />
                  <span className="text-[10px] uppercase font-extrabold font-mono text-zinc-400 tracking-wider">
                    Targeted Study Exam Set ({questions.length} questions)
                  </span>
                </div>

                <div className="space-y-4 select-text">
                  {questions.map((q, idx) => (
                    <QuestionCard key={idx} question={q} index={idx} />
                  ))}
                </div>
              </div>
            )}

          </div>
        </div>
      </main>

      {/* Global Toast alerts */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 select-none pointer-events-none max-w-sm" role="alert" aria-live="assertive">
        {error && (
          <div className="rounded-lg border border-red-900 bg-red-950/80 backdrop-blur-md px-4 py-3 text-xs text-red-400 flex items-center gap-2 pointer-events-auto shadow-lg">
            <X className="h-4 w-4 text-red-400 shrink-0" />
            <span className="select-text">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-400 pointer-events-auto" aria-label="Dismiss error">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

    </div>
  );
}

function QuestionCard({ question, index }: { question: any; index: number }) {
  const [showAnswer, setShowAnswer] = useState(false);

  return (
    <div className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-5 space-y-4 select-text transition shadow-inner">
      <div className="flex items-start gap-3">
        <span className="flex items-center justify-center h-6 w-6 rounded-lg bg-zinc-900 border border-zinc-800 text-[10px] font-extrabold font-mono text-zinc-450 shrink-0">
          Q{index + 1}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-xs md:text-sm font-semibold text-zinc-200 leading-relaxed whitespace-pre-wrap select-text">
            {question.question || question.text || "Untitled Question"}
          </p>
        </div>
      </div>

      {/* Render Options if Multiple Choice */}
      {question.options && Array.isArray(question.options) && (
        <div className="space-y-1.5 pl-9 select-none">
          {question.options.map((opt: string, i: number) => {
            const letter = String.fromCharCode(65 + i);
            const isCorrect = showAnswer && (
              question.correct_answer === opt || 
              question.correct_answer === letter
            );
            return (
              <div 
                key={i} 
                className={`p-2.5 rounded-lg border text-xs flex gap-2.5 transition duration-300 ${
                  isCorrect 
                    ? "border-emerald-500/30 bg-emerald-950/15 text-emerald-300" 
                    : "border-zinc-900/60 bg-zinc-950/20 text-zinc-450 hover:bg-zinc-900/40 hover:text-zinc-300"
                }`}
              >
                <span className={`font-mono font-bold ${isCorrect ? "text-emerald-400" : "text-zinc-400"}`}>
                  {letter}.
                </span>
                <span className="leading-normal font-medium">{opt}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Accordion Action buttons */}
      <div className="pl-9 select-none pt-1">
        <button
          onClick={() => setShowAnswer(!showAnswer)}
          className="flex items-center gap-1 text-[10px] font-mono text-indigo-400/90 hover:text-indigo-300 transition-colors focus:outline-none"
          aria-expanded={showAnswer}
        >
          {showAnswer ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          <span>{showAnswer ? "COLLAPSE EXPLANATION" : "REVEAL EXPLANATION"}</span>
        </button>

        {showAnswer && (
          <div className="mt-3.5 p-4 rounded-xl bg-zinc-950/80 border border-zinc-900/60 space-y-3 animate-slide-in">
            <div className="flex items-center gap-1.5 font-mono text-[9px] text-zinc-500 uppercase border-b border-zinc-900 pb-1.5 select-none">
              <Info className="h-3.5 w-3.5 text-indigo-400" />
              <span>Correct Answer & Diagnostic</span>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-bold text-zinc-200 select-text leading-relaxed">
                {question.correct_answer || question.answer}
              </p>
              {question.explanation && (
                <p className="text-xs text-zinc-450 leading-relaxed font-sans select-text border-l border-zinc-800 pl-2.5">
                  {question.explanation}
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
