"use client";

import { useState, useEffect } from "react";
import { FileQuestion, GraduationCap, ListChecks, Loader2, BookOpen, ChevronDown, ChevronUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";

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

  const handleGenerate = async () => {
    if (!topic.trim()) {
      setError("Please enter a topic.");
      return;
    }

    setIsGenerating(true);
    setError(null);
    setQuestions([]);

    try {
      const res = await fetch("/api/v1/questions/generate", {
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
        throw new Error("Failed to generate questions");
      }

      const data = await res.json();
      setQuestions(data.questions || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 max-w-4xl mx-auto w-full">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Question Generator
        </h1>
        <p className="text-sm text-zinc-500">
          Generate practice questions from your knowledge base. Supports custom
          and exam-mimicry modes for targeted study preparation.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Configuration Sidebar */}
        <div className="md:col-span-4 flex flex-col gap-4">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-5">
            <h3 className="text-sm font-medium text-zinc-300 mb-4">
              Configuration
            </h3>

            {/* Knowledge Base */}
            <div className="mb-4">
              <label className="text-xs text-zinc-500 mb-2 block">
                Knowledge Base
              </label>
              <select
                value={kbName}
                onChange={(e) => setKbName(e.target.value)}
                className="w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {kbs.length === 0 ? (
                  <option value="default">default</option>
                ) : (
                  kbs.map((kb) => (
                    <option key={kb.name} value={kb.name}>
                      {kb.name}
                    </option>
                  ))
                )}
              </select>
            </div>

            {/* Topic */}
            <div className="mb-4">
              <label className="text-xs text-zinc-500 mb-2 block">
                Topic / Concept
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. Backpropagation"
                className="w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 placeholder:text-zinc-600"
              />
            </div>

            {/* Question type */}
            <div className="mb-4">
              <label className="text-xs text-zinc-500 mb-2 block">
                Question Type
              </label>
              <div className="grid grid-cols-2 gap-2">
                {QUESTION_TYPES.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => setType(t.value)}
                    className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs transition-colors ${
                      type === t.value
                        ? "border-indigo-500 bg-indigo-500/10 text-indigo-300"
                        : "border-zinc-800 bg-zinc-900 text-zinc-400 hover:bg-zinc-800"
                    }`}
                  >
                    {t.value === "mimic" ? (
                      <GraduationCap className="h-4 w-4" />
                    ) : (
                      <FileQuestion className="h-4 w-4" />
                    )}
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {type === "mimic" && (
              <div className="mb-4">
                <label className="text-xs text-zinc-500 mb-2 block">
                  Reference Exam Text (Optional)
                </label>
                <textarea
                  value={referenceExam}
                  onChange={(e) => setReferenceExam(e.target.value)}
                  placeholder="Paste a sample question or exam instructions here to mimic its style..."
                  className="w-full h-20 rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none placeholder:text-zinc-600"
                />
              </div>
            )}

            {/* Difficulty */}
            <div className="mb-4">
              <label className="text-xs text-zinc-500 mb-2 block">
                Difficulty
              </label>
              <div className="flex gap-2">
                {DIFFICULTIES.map((d) => (
                  <button
                    key={d.value}
                    onClick={() => setDifficulty(d.value)}
                    className={`flex-1 rounded-md px-3 py-1.5 text-xs transition-colors ${
                      difficulty === d.value
                        ? "bg-zinc-100 text-zinc-900 font-semibold"
                        : "border border-zinc-800 bg-zinc-900 text-zinc-400 hover:bg-zinc-800"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Count slider */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-zinc-500">Number of Questions</label>
                <span className="text-xs font-mono text-zinc-300">{count}</span>
              </div>
              <input
                type="range"
                min={1}
                max={20}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-full accent-indigo-500"
              />
              <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
                <span>1</span>
                <span>20</span>
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={isGenerating || !topic.trim()}
              className="w-full flex justify-center items-center gap-1.5 rounded bg-zinc-100 px-4 py-2.5 text-xs font-semibold text-zinc-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <ListChecks className="h-4 w-4" />
                  Generate Questions
                </>
              )}
            </button>
            {error && (
              <p className="text-red-400 text-xs mt-2 text-center">{error}</p>
            )}
          </div>
        </div>

        {/* Results Area */}
        <div className="md:col-span-8">
          {questions.length > 0 ? (
            <div className="space-y-4">
              <h3 className="text-lg font-medium text-zinc-200">Generated Questions</h3>
              {questions.map((q, idx) => (
                <QuestionCard key={idx} question={q} index={idx} />
              ))}
            </div>
          ) : (
            <div className="h-full min-h-[300px] flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-800 bg-zinc-900/20 text-center p-8">
              <BookOpen className="h-10 w-10 text-zinc-700 mb-4" />
              <h3 className="text-sm font-medium text-zinc-400 mb-1">No Questions Yet</h3>
              <p className="text-xs text-zinc-600 max-w-[250px]">
                Configure your options on the left and click "Generate Questions" to create a practice set.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function QuestionCard({ question, index }: { question: any; index: number }) {
  const [showAnswer, setShowAnswer] = useState(false);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-5 transition-all">
      <div className="flex items-start gap-3">
        <span className="flex items-center justify-center h-6 w-6 rounded-full bg-zinc-800 text-xs font-medium text-zinc-300 shrink-0">
          {index + 1}
        </span>
        <div className="flex-1">
          <p className="text-sm text-zinc-200 mb-4 leading-relaxed">
            {question.question || question.text || "Untitled Question"}
          </p>

          {/* Render Options if MCQ */}
          {question.options && Array.isArray(question.options) && (
            <div className="space-y-2 mb-4">
              {question.options.map((opt: string, i: number) => {
                const isCorrect = showAnswer && (
                  question.correct_answer === opt || 
                  question.correct_answer === String.fromCharCode(65 + i)
                );
                return (
                  <div 
                    key={i} 
                    className={`p-2 rounded border text-sm flex gap-2 ${
                      isCorrect 
                        ? "border-green-500/50 bg-green-500/10 text-green-300" 
                        : "border-zinc-800/80 bg-zinc-900 text-zinc-400"
                    }`}
                  >
                    <span className="font-mono text-zinc-500">{String.fromCharCode(65 + i)}.</span>
                    <span>{opt}</span>
                  </div>
                );
              })}
            </div>
          )}

          <button
            onClick={() => setShowAnswer(!showAnswer)}
            className="flex items-center gap-1 text-xs font-medium text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            {showAnswer ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {showAnswer ? "Hide Answer & Explanation" : "Show Answer & Explanation"}
          </button>

          {showAnswer && (
            <div className="mt-4 p-4 rounded-md bg-zinc-950 border border-zinc-800">
              <div className="mb-2">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Correct Answer:</span>
                <p className="text-sm text-zinc-200 mt-1">{question.correct_answer || question.answer}</p>
              </div>
              {question.explanation && (
                <div className="mt-3 pt-3 border-t border-zinc-800/50">
                  <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Explanation:</span>
                  <p className="text-sm text-zinc-400 mt-1 leading-relaxed">{question.explanation}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
