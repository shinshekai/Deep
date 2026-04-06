"use client";

import { useState } from "react";
import { FileQuestion, GraduationCap, ListChecks } from "lucide-react";
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
  const [count, setCount] = useState(5);
  const [type, setType] = useState("mcq");
  const [difficulty, setDifficulty] = useState("medium");

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Question Generator
        </h1>
        <p className="text-sm text-zinc-500">
          Generate practice questions from your knowledge base. Supports custom
          and exam-mimicry modes for targeted study preparation.
        </p>
      </div>

      {/* Generator form */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-5">
        <h3 className="text-sm font-medium text-zinc-300 mb-4">
          Configuration
        </h3>

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
                className={`rounded-md px-3 py-1.5 text-xs transition-colors ${
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
        <div className="mb-4">
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
          disabled
          className="flex items-center gap-1.5 rounded bg-zinc-100 px-4 py-2 text-xs font-semibold text-zinc-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ListChecks className="h-4 w-4" />
          Generate Questions
        </button>
      </div>

      {/* Info card */}
      <div className="rounded-lg border border-zinc-800/50 bg-zinc-900/30 p-4">
        <h4 className="text-xs font-semibold text-zinc-500 mb-2">API Endpoints</h4>
        <div className="space-y-1 font-mono text-[11px] text-zinc-600">
          <p>
            <Badge variant="zinc" className="text-[10px] mx-1">POST</Badge>
            /api/v1/questions/generate
          </p>
          <p className="mt-2 text-zinc-500 font-sans">
            Connect the backend to generate questions from your knowledge base.
          </p>
        </div>
      </div>
    </div>
  );
}
