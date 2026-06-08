"use client";

import { useState, useEffect } from "react";
import {
  BookMarked,
  Plus,
  Brain,
  Sparkles,
  Lightbulb,
  Loader2,
  X,
  BookOpen,
} from "lucide-react";
import { API_BASE_URL, secureFetch } from "@/lib/config";

type NotebookNote = {
  id: string;
  content: string;
  source: string;
  timestamp: number;
};

type Notebook = {
  id: string;
  title: string;
  description: string;
  notes: NotebookNote[];
  created_at: number;
  updated_at: number;
};

interface ChatInferenceDisplayProps {
  selectedNbId: string | null;
  onNotebookChange: (id: string | null) => void;
  refreshKey: number;
  setErrorMsg: (msg: string | null) => void;
  setSuccessMsg: (msg: string | null) => void;
}

export function ChatInferenceDisplay({
  selectedNbId,
  onNotebookChange,
  refreshKey,
  setErrorMsg,
  setSuccessMsg,
}: ChatInferenceDisplayProps) {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [showCreateNbModal, setShowCreateNbModal] = useState(false);
  const [newNbTitle, setNewNbTitle] = useState("");
  const [newNbDesc, setNewNbDesc] = useState("");
  const [creatingNb, setCreatingNb] = useState(false);
  const [noteInput, setNoteInput] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [isGeneratingIdeas, setIsGeneratingIdeas] = useState(false);
  const [generatedIdeas, setGeneratedIdeas] = useState<string[]>([]);
  const [ideaModel, setIdeaModel] = useState("Qwen3-1.7B-Q4_K_M");
  const [availableModels, setAvailableModels] = useState<
    Record<string, unknown>[]
  >([]);

  const loadNotebooks = async () => {
    try {
      const res = await secureFetch(`${API_BASE_URL}/notebooks`);
      if (res.ok) {
        const data = await res.json();
        setNotebooks(data);
        if (data.length > 0 && !selectedNbId) {
          onNotebookChange(data[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const loadModels = async () => {
    try {
      const res = await secureFetch(`${API_BASE_URL}/models`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setAvailableModels(data);
        }
      }
    } catch {}
  };

  useEffect(() => {
    loadNotebooks();
    loadModels();
  }, []);

  useEffect(() => {
    if (refreshKey > 0) loadNotebooks();
  }, [refreshKey]);

  useEffect(() => {
    if (showCreateNbModal) {
      const timer = setTimeout(() => {
        const el = document.querySelector<HTMLElement>(
          '[aria-label="Construct Notebook"] input[aria-label="Notebook title"]'
        );
        el?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [showCreateNbModal]);

  const activeNotebook = notebooks.find((n) => n.id === selectedNbId);

  const handleCreateNotebook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNbTitle.trim()) return;
    setCreatingNb(true);
    setErrorMsg(null);
    try {
      const res = await secureFetch(`${API_BASE_URL}/notebooks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newNbTitle, description: newNbDesc }),
      });
      if (!res.ok) throw new Error("Failed to construct notebook schema.");
      const data = await res.json();
      setNotebooks((prev) => [...prev, data]);
      onNotebookChange(data.id);
      setNewNbTitle("");
      setNewNbDesc("");
      setShowCreateNbModal(false);
      setSuccessMsg("Notebook constructed successfully.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error ? err.message : "Failed to construct notebook."
      );
    } finally {
      setCreatingNb(false);
    }
  };

  const handleSaveNote = async () => {
    if (!selectedNbId || !noteInput.trim()) return;
    setSavingNote(true);
    setErrorMsg(null);
    try {
      const res = await secureFetch(
        `${API_BASE_URL}/notebooks/${selectedNbId}/notes`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: noteInput.trim() }),
        }
      );
      if (!res.ok) throw new Error("Failed to write note.");
      await loadNotebooks();
      setNoteInput("");
      setSuccessMsg("Research note saved.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error ? err.message : "Failed to write note."
      );
    } finally {
      setSavingNote(false);
    }
  };

  const handleSynthesizeProposals = async () => {
    const activeNb = notebooks.find((n) => n.id === selectedNbId);
    if (!activeNb || activeNb.notes.length === 0) {
      setErrorMsg(
        "Add notes or save responses to this Notebook before synthesis."
      );
      return;
    }
    setIsGeneratingIdeas(true);
    setErrorMsg(null);
    setGeneratedIdeas([]);
    try {
      const res = await secureFetch(`${API_BASE_URL}/ideagen/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          notebook_ids: [selectedNbId],
          model_id: ideaModel,
        }),
      });
      if (!res.ok) throw new Error("Synthesis service failed.");
      const data = await res.json();
      setGeneratedIdeas(data.ideas || []);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Failed to generate conceptual links."
      );
    } finally {
      setIsGeneratingIdeas(false);
    }
  };

  return (
    <>
      <aside className="w-80 shrink-0 border-l border-zinc-900 bg-zinc-950/60 backdrop-blur-sm flex flex-col h-full overflow-hidden select-none animate-slide-in">
        <div className="p-4 border-b border-zinc-900 flex items-center justify-between">
          <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono flex items-center gap-1.5">
            <BookMarked className="h-4 w-4 text-indigo-400" />
            Notebook Annotations
          </span>
          <button
            onClick={() => setShowCreateNbModal(true)}
            className="p-1 rounded-lg border border-zinc-900 hover:border-zinc-800 text-zinc-400 hover:text-white transition"
            title="Construct Notebook"
            aria-label="Open construct notebook"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <div className="space-y-1.5">
            <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
              Target Notebook
            </label>
            <select
              value={selectedNbId || ""}
              onChange={(e) => onNotebookChange(e.target.value || null)}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-sans"
              aria-label="Select target notebook"
            >
              {notebooks.length === 0 ? (
                <option value="">No Notebooks</option>
              ) : (
                notebooks.map((nb) => (
                  <option key={nb.id} value={nb.id}>
                    {nb.title}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
              Notes Timeline ({activeNotebook?.notes.length || 0})
            </label>
            {!activeNotebook ? (
              <div className="rounded-lg border border-dashed border-zinc-900 p-6 text-center text-zinc-500 text-xs">
                Create a notebook to capture thoughts.
              </div>
            ) : activeNotebook.notes.length === 0 ? (
              <div className="rounded-lg border border-dashed border-zinc-900 p-6 text-center text-zinc-500 text-xs">
                Notebook is empty. Save response or write note below.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[220px] overflow-y-auto pr-1">
                {activeNotebook.notes.map((note) => (
                  <div
                    key={note.id}
                    className="rounded-lg border border-zinc-900 bg-zinc-950/40 p-3 space-y-1.5 text-zinc-300 text-[11px] leading-relaxed relative"
                  >
                    <p className="whitespace-pre-wrap font-sans select-text">
                      {note.content.substring(0, 200)}
                      {note.content.length > 200 && "..."}
                    </p>
                    <div className="flex items-center justify-between text-[9px] font-mono text-zinc-600 border-t border-zinc-900/60 pt-1.5 mt-1 select-none">
                      <span className="capitalize text-indigo-400">
                        Src: {note.source}
                      </span>
                      <span>
                        {new Date(note.timestamp * 1000).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {activeNotebook && (
            <div className="space-y-2.5 border-t border-zinc-900/60 pt-3">
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono block">
                Add Research Note
              </label>
              <textarea
                value={noteInput}
                onChange={(e) => setNoteInput(e.target.value)}
                placeholder="Draft insights, paste quotes, or add custom conceptual highlights..."
                rows={2}
                disabled={savingNote}
                className="w-full rounded-lg border border-zinc-850 bg-zinc-950 p-2.5 text-xs text-zinc-200 placeholder-zinc-700 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 resize-none font-sans"
                aria-label="Draft note content"
              />
              <div className="flex justify-end select-none">
                <button
                  onClick={handleSaveNote}
                  disabled={savingNote || !noteInput.trim()}
                  className="flex items-center gap-1.5 rounded-lg bg-zinc-100 px-3 py-1.5 text-[10px] font-bold text-zinc-900 hover:bg-white transition disabled:opacity-40"
                  aria-label="Save note"
                >
                  {savingNote ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Plus className="h-3.5 w-3.5" />
                  )}
                  <span>Save Note</span>
                </button>
              </div>
            </div>
          )}

          {activeNotebook && activeNotebook.notes.length > 0 && (
            <div className="space-y-3.5 border-t border-zinc-900/60 pt-4">
              <div className="flex items-center gap-1 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono">
                <Brain className="h-3.5 w-3.5 text-indigo-400 animate-pulse" />
                <span>Synthesize Concept ideas</span>
              </div>
              <div className="space-y-2 select-text">
                <label className="text-[9px] uppercase font-bold text-zinc-600 tracking-wider font-mono block">
                  Synthesis Model
                </label>
                <select
                  value={ideaModel}
                  onChange={(e) => setIdeaModel(e.target.value)}
                  className="w-full rounded-lg border border-zinc-900 bg-zinc-950 px-2.5 py-1.5 text-[10px] text-zinc-300 focus:outline-none"
                  aria-label="Select synthesis model"
                >
                  {availableModels.length === 0 ? (
                    <>
                      <option value="Qwen3-1.7B-Q4_K_M">
                        Qwen3-1.7B (Q4_K_M)
                      </option>
                      <option value="Qwen3-8B">Qwen3-8B</option>
                    </>
                  ) : (
                    availableModels.map((m) => (
                      <option key={String(m.id)} value={String(m.id)}>
                        {String(m.name)} ({String(m.tier)})
                      </option>
                    ))
                  )}
                </select>
              </div>
              <button
                onClick={handleSynthesizeProposals}
                disabled={isGeneratingIdeas}
                className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600/20 border border-indigo-500/30 hover:bg-indigo-600/35 px-3 py-2 text-xs font-bold text-indigo-300 transition disabled:opacity-40"
                aria-label="Generate project ideas"
              >
                {isGeneratingIdeas ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Synthesizing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-3.5 w-3.5" />
                    <span>Generate Project Ideas</span>
                  </>
                )}
              </button>
            </div>
          )}

          {generatedIdeas.length > 0 && (
            <div className="space-y-2 border-t border-zinc-900/60 pt-4 animate-slide-in">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-emerald-400 font-mono flex items-center gap-1">
                  <Lightbulb className="h-3.5 w-3.5 text-emerald-400" />
                  Proposals Synthesized
                </span>
                <button
                  onClick={() => setGeneratedIdeas([])}
                  className="text-zinc-600 hover:text-zinc-400 text-xs"
                  aria-label="Clear generated ideas"
                >
                  Clear
                </button>
              </div>
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {generatedIdeas.map((idea, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg border border-emerald-950/60 bg-emerald-950/5 p-3 space-y-1 text-zinc-300 text-[11px] leading-relaxed relative"
                  >
                    <p className="font-semibold text-emerald-400">
                      Proposal #{idx + 1}
                    </p>
                    <p className="select-text mt-1">{idea}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </aside>

      {showCreateNbModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm select-none"
          role="dialog"
          aria-modal="true"
          aria-label="Construct Notebook"
          onKeyDown={(e) => {
            if (e.key === "Escape") setShowCreateNbModal(false);
            if (e.key === "Tab") {
              const modal = e.currentTarget.querySelector("form");
              if (!modal) return;
              const focusable = modal.querySelectorAll<HTMLElement>(
                'input, textarea, button:not([disabled]), [tabindex]:not([tabindex="-1"])'
              );
              if (focusable.length === 0) return;
              const first = focusable[0];
              const last = focusable[focusable.length - 1];
              if (e.shiftKey) {
                if (document.activeElement === first) {
                  e.preventDefault();
                  last.focus();
                }
              } else {
                if (document.activeElement === last) {
                  e.preventDefault();
                  first.focus();
                }
              }
            }
          }}
        >
          <form
            onSubmit={handleCreateNotebook}
            className="w-full max-w-md rounded-xl border border-zinc-900 bg-zinc-950 p-6 space-y-4 shadow-xl"
          >
            <div className="flex items-center justify-between border-b border-zinc-900 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-1.5 font-mono uppercase tracking-wider">
                <BookOpen className="h-4.5 w-4.5 text-indigo-400" />
                Construct Notebook
              </h3>
              <button
                type="button"
                onClick={() => setShowCreateNbModal(false)}
                className="text-zinc-500 hover:text-zinc-350 transition"
                aria-label="Close notebook modal"
              >
                <X className="h-4.5 w-4.5" />
              </button>
            </div>

            <div className="space-y-3 select-text">
              <div>
                <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono mb-1.5 block">
                  Notebook Title
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Quantum Ingestion Core"
                  value={newNbTitle}
                  onChange={(e) => setNewNbTitle(e.target.value)}
                  className="w-full rounded-lg border border-zinc-900 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none"
                  aria-label="Notebook title"
                />
              </div>

              <div>
                <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono mb-1.5 block">
                  Notebook Description
                </label>
                <textarea
                  placeholder="Summary of research themes, study guidelines or annotation references..."
                  rows={3}
                  value={newNbDesc}
                  onChange={(e) => setNewNbDesc(e.target.value)}
                  className="w-full rounded-lg border border-zinc-900 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 placeholder-zinc-700 focus:outline-none resize-none font-sans"
                  aria-label="Notebook description"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-zinc-900 pt-4">
              <button
                type="button"
                onClick={() => setShowCreateNbModal(false)}
                className="rounded-lg border border-zinc-900 px-4 py-1.5 text-xs font-semibold text-zinc-400 hover:bg-zinc-900 transition"
                aria-label="Cancel notebook creation"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creatingNb || !newNbTitle.trim()}
                className="flex items-center gap-1.5 rounded-lg bg-indigo-650 px-4 py-1.5 text-xs font-bold text-white hover:opacity-90 transition disabled:opacity-40"
                aria-label="Create notebook"
              >
                {creatingNb ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Creating...</span>
                  </>
                ) : (
                  <span>Construct</span>
                )}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
