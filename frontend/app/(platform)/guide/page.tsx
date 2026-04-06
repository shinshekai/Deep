"use client";

import { useState } from "react";
import { BookOpen, MessageSquare, Target, ClipboardList } from "lucide-react";

const MODES = [
  { value: "interactive", label: "Interactive" },
  { value: "lecture", label: "Lecture" },
  { value: "quiz", label: "Quiz" },
];

export default function GuidedLearningPage() {
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState("interactive");

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Guided Learning
        </h1>
        <p className="text-sm text-zinc-500">
          Structured learning sessions that walk you through document content
          step by step. Four-phase flow: Locate &rarr; Interactive &rarr; Chat
          &rarr; Summary.
        </p>
      </div>

      {/* Learning flow */}
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          { icon: Target, phase: "Locate", desc: "Find relevant sections" },
          { icon: BookOpen, phase: "Interactive", desc: "Explore content" },
          { icon: MessageSquare, phase: "Chat", desc: "Ask questions" },
          { icon: ClipboardList, phase: "Summary", desc: "Review & recap" },
        ].map(({ icon: Icon, phase, desc }) => (
          <div
            key={phase}
            className="flex flex-col items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 text-center"
          >
            <Icon className="h-5 w-5 text-indigo-400" />
            <p className="text-xs font-medium text-zinc-300">{phase}</p>
            <p className="text-[11px] text-zinc-600">{desc}</p>
          </div>
        ))}
      </div>

      {/* Start session form */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-3">
          New Learning Session
        </h3>
        <div className="flex flex-col gap-3">
          <input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="What would you like to learn about?"
            className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <div className="flex gap-2">
            {MODES.map((m) => (
              <button
                key={m.value}
                onClick={() => setMode(m.value)}
                className={`rounded-md px-3 py-1.5 text-xs transition-colors ${
                  mode === m.value
                    ? "bg-zinc-100 text-zinc-900 font-semibold"
                    : "border border-zinc-800 bg-zinc-900 text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <button
            disabled={!topic.trim()}
            className="self-end rounded bg-zinc-100 px-4 py-1.5 text-xs font-semibold text-zinc-900 transition-colors hover:bg-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            Start Session
          </button>
        </div>
      </div>

      {/* Session history placeholder */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-6">
        <h3 className="text-sm font-medium text-zinc-500 mb-3">
          Session History
        </h3>
        <div className="rounded-md border border-zinc-800/50 bg-zinc-900/30 p-4 text-center">
          <p className="text-xs text-zinc-600">
            No past sessions. Start one above.
          </p>
        </div>
      </div>
    </div>
  );
}
