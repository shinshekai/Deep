"use client";

import { useState, useEffect } from "react";
import { BookOpen, Plus, Loader2, Sparkles, Calendar, PlusCircle, AlignLeft, CheckSquare, Square, Lightbulb, X, Brain } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { API_BASE_URL, secureFetch } from "@/lib/config";

type Note = {
  id: string;
  content: string;
  source: string;
  timestamp: number;
};

type Notebook = {
  id: string;
  title: string;
  description: string;
  notes: Note[];
  created_at: number;
  updated_at: number;
};

export default function NotebooksPage() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [selectedNbId, setSelectedNbId] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [isCreatingNb, setIsCreatingNb] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Note addition
  const [noteContent, setNoteContent] = useState("");
  const [isSavingNote, setIsSavingNote] = useState(false);

  // Idea Generation
  const [selectedForIdeaGen, setSelectedForIdeaGen] = useState<Record<string, boolean>>({});
  const [isGeneratingIdeas, setIsGeneratingIdeas] = useState(false);
  const [generatedIdeas, setGeneratedIdeas] = useState<string[]>([]);
  const [ideaModel, setIdeaModel] = useState("Qwen3-1.7B-Q4_K_M");
  const [models, setModels] = useState<Record<string, unknown>[]>([]);

  // Errors / Info
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadNotebooks();
    loadModels();
  }, []);

  const loadNotebooks = async () => {
    try {
      const res = await secureFetch(`${API_BASE_URL}/notebooks`);
      if (res.ok) {
        const data = await res.json();
        setNotebooks(data);
        if (data.length > 0 && !selectedNbId) {
          setSelectedNbId(data[0].id);
        }
      }
    } catch (e) {
      console.error("Failed to load notebooks", e);
    }
  };

  const loadModels = async () => {
    try {
      const res = await secureFetch(`${API_BASE_URL}/models`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setModels(data);
        }
      }
    } catch {}
  };

  const handleCreateNotebook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    setIsCreatingNb(true);
    setError(null);
    try {
      const res = await secureFetch(`${API_BASE_URL}/notebooks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle, description: newDesc }),
      });

      if (!res.ok) throw new Error("Failed to create notebook");
      const data = await res.json();
      setNotebooks((prev) => [...prev, data]);
      setSelectedNbId(data.id);
      setNewTitle("");
      setNewDesc("");
      setShowCreateModal(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create notebook");
    } finally {
      setIsCreatingNb(false);
    }
  };

  const handleSaveNote = async () => {
    if (!selectedNbId || !noteContent.trim()) return;

    setIsSavingNote(true);
    setError(null);
    try {
      const res = await secureFetch(`${API_BASE_URL}/notebooks/${selectedNbId}/notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: noteContent }),
      });

      if (!res.ok) throw new Error("Failed to save note");
      
      // Reload notebooks to get updated notes list
      await loadNotebooks();
      setNoteContent("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save note");
    } finally {
      setIsSavingNote(false);
    }
  };

  const handleGenerateIdeas = async () => {
    const ids = Object.keys(selectedForIdeaGen).filter((id) => selectedForIdeaGen[id]);
    if (ids.length === 0) {
      setError("Please select at least one notebook for idea generation.");
      return;
    }

    setIsGeneratingIdeas(true);
    setError(null);
    setGeneratedIdeas([]);
    try {
      const res = await secureFetch(`${API_BASE_URL}/ideagen/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          notebook_ids: ids,
          model_id: ideaModel,
        }),
      });

      if (!res.ok) throw new Error("Failed to generate ideas");
      const data = await res.json();
      setGeneratedIdeas(data.ideas || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate ideas");
    } finally {
      setIsGeneratingIdeas(false);
    }
  };

  const toggleSelectNotebook = (id: string) => {
    setSelectedForIdeaGen((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const activeNotebook = notebooks.find((n) => n.id === selectedNbId);

  return (
    <div className="flex flex-col gap-6 p-6 max-w-6xl mx-auto w-full">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-indigo-500" />
            Notebook Lab
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Store research findings, paste snippets, and synthesize new conceptual links or project ideas.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-indigo-500 shadow-md shadow-indigo-600/20 w-fit shrink-0"
        >
          <Plus className="h-4 w-4" />
          New Notebook
        </button>
      </div>

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left column: Notebooks List & IdeaGen trigger */}
        <div className="lg:col-span-4 flex flex-col gap-5">
          
          {/* Notebooks List */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 backdrop-blur-md p-4">
            <div className="flex items-center justify-between border-b border-zinc-850 pb-3 mb-3">
              <span className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono">Notebooks</span>
              <Badge variant="zinc" className="text-[10px] text-zinc-500 border-zinc-800">
                {notebooks.length} total
              </Badge>
            </div>

            {notebooks.length === 0 ? (
              <div className="text-center py-8">
                <BookOpen className="h-8 w-8 text-zinc-700 mx-auto mb-2" />
                <p className="text-xs text-zinc-500">No notebooks yet</p>
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="mt-2 text-xs text-indigo-400 hover:text-indigo-300 font-semibold underline"
                >
                  Create one now
                </button>
              </div>
            ) : (
              <div className="space-y-1.5 max-h-[300px] overflow-y-auto pr-1">
                {notebooks.map((nb) => {
                  const isSelected = nb.id === selectedNbId;
                  const isChecked = !!selectedForIdeaGen[nb.id];
                  return (
                    <div
                      key={nb.id}
                      className={`group flex items-center justify-between rounded-lg border p-2.5 transition text-left cursor-pointer ${
                        isSelected
                          ? "bg-indigo-950/20 border-indigo-500/30 text-indigo-200"
                          : "border-zinc-850 bg-zinc-950/20 text-zinc-400 hover:bg-zinc-900/30 hover:border-zinc-800"
                      }`}
                      onClick={() => setSelectedNbId(nb.id)}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSelectNotebook(nb.id);
                          }}
                          className="text-zinc-500 hover:text-zinc-300 transition shrink-0"
                          title="Select for Idea Generation"
                        >
                          {isChecked ? (
                            <CheckSquare className="h-4 w-4 text-indigo-500" />
                          ) : (
                            <Square className="h-4 w-4 text-zinc-500" />
                          )}
                        </button>
                        <div className="min-w-0">
                          <p className={`text-xs font-semibold truncate ${isSelected ? "text-indigo-300" : "text-zinc-200"}`}>
                            {nb.title}
                          </p>
                          <p className="text-[10px] text-zinc-500 truncate mt-0.5">
                            {nb.notes.length} note{nb.notes.length !== 1 && "s"}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Idea Generation Panel */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 backdrop-blur-md p-4 space-y-4">
            <div className="flex items-center gap-1.5 text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono border-b border-zinc-850 pb-3">
              <Brain className="h-4 w-4 text-indigo-400" />
              <span>Idea Generator</span>
            </div>

            <p className="text-xs text-zinc-500 leading-normal">
              Select multiple notebooks using the checkboxes, pick a model, and automatically synthesize novel project proposals.
            </p>

            {/* Model select */}
            <div>
              <label className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider font-mono mb-1.5 block">
                Synthesis Model
              </label>
              <select
                value={ideaModel}
                onChange={(e) => setIdeaModel(e.target.value)}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {models.length === 0 ? (
                  <>
                    <option value="Qwen3-1.7B-Q4_K_M">Qwen3-1.7B (Q4_K_M)</option>
                    <option value="Qwen3-8B">Qwen3-8B (Semi-Resident)</option>
                    <option value="Qwen3-30B-A3B">Qwen3-30B (MoE T3)</option>
                  </>
                ) : (
                  models.map((m) => (
                    <option key={String(m.id)} value={String(m.id)}>
                      {String(m.name || m.id)} ({String(m.tier)})
                    </option>
                  ))
                )}
              </select>
            </div>

            <button
              onClick={handleGenerateIdeas}
              disabled={isGeneratingIdeas || Object.values(selectedForIdeaGen).filter(Boolean).length === 0}
              className="w-full flex items-center justify-center gap-1.5 rounded-lg bg-indigo-600/25 border border-indigo-500/35 hover:bg-indigo-600/40 px-4 py-2.5 text-xs font-semibold text-indigo-200 transition disabled:opacity-40 disabled:cursor-not-allowed shadow-inner"
            >
              {isGeneratingIdeas ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />
                  Synthesizing Ideas...
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                  Generate Ideas ({Object.values(selectedForIdeaGen).filter(Boolean).length})
                </>
              )}
            </button>
          </div>

        </div>

        {/* Right column: Selected Notebook Content & Notes Editor */}
        <div className="lg:col-span-8 space-y-6">
          
          {/* Active Notebook Details */}
          {activeNotebook ? (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 backdrop-blur-md p-5 space-y-5">
              
              {/* Title / Description info */}
              <div className="border-b border-zinc-850 pb-4 flex flex-col md:flex-row md:items-start justify-between gap-3">
                <div className="space-y-1">
                  <h2 className="text-lg font-bold text-white tracking-tight">{activeNotebook.title}</h2>
                  <p className="text-xs text-zinc-400 leading-relaxed max-w-xl">
                    {activeNotebook.description || "No description provided."}
                  </p>
                </div>
                <div className="flex items-center gap-1.5 font-mono text-[10px] text-zinc-400 mt-1">
                  <Calendar className="h-3 w-3" />
                  <span>Created: {new Date(activeNotebook.created_at * 1000).toLocaleDateString()}</span>
                </div>
              </div>

              {/* Notes Timeline */}
              <div className="space-y-4">
                <h3 className="text-xs uppercase font-extrabold text-zinc-400 tracking-wider font-mono">Notes Timeline</h3>
                
                {activeNotebook.notes.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-zinc-800 p-8 text-center bg-zinc-950/10">
                    <AlignLeft className="h-6 w-6 text-zinc-700 mx-auto mb-2" />
                    <p className="text-xs text-zinc-500">This notebook is empty. Write your first note below.</p>
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
                    {activeNotebook.notes.map((note) => (
                      <div
                        key={note.id}
                        className="rounded-lg border border-zinc-850 bg-zinc-950/20 p-3.5 space-y-2 text-zinc-300"
                      >
                        <p className="text-xs leading-relaxed whitespace-pre-wrap select-text">{note.content}</p>
                        <div className="flex items-center justify-between text-[9px] font-mono text-zinc-400 border-t border-zinc-900/60 pt-2 mt-1">
                          <span className="capitalize">Source: {note.source}</span>
                          <span>{new Date(note.timestamp * 1000).toLocaleString()}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Notes Editor form */}
              <div className="border-t border-zinc-850 pt-4 space-y-3">
                <label className="text-xs font-semibold text-zinc-300 block">Add Note</label>
                <textarea
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  placeholder="Type or paste markdown snippets, facts, citations or general notes..."
                  rows={3}
                  disabled={isSavingNote}
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-200 placeholder-zinc-650 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 disabled:opacity-50 resize-none font-sans"
                />
                
                <div className="flex justify-end">
                  <button
                    onClick={handleSaveNote}
                    disabled={isSavingNote || !noteContent.trim()}
                    className="flex items-center gap-1.5 rounded-lg bg-zinc-100 px-4.5 py-1.5 text-xs font-semibold text-zinc-950 hover:bg-white transition disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    {isSavingNote ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <PlusCircle className="h-3.5 w-3.5" />
                        Save Note
                      </>
                    )}
                  </button>
                </div>
              </div>

            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-900/10 p-12 text-center">
              <BookOpen className="h-10 w-10 text-zinc-700 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-zinc-400">No notebook selected</h3>
              <p className="text-xs text-zinc-600 mt-1 max-w-sm mx-auto">
                Create a notebook or select an existing one from the left-hand panel to start adding research notes.
              </p>
            </div>
          )}

          {/* Generated Ideas Result */}
          {generatedIdeas.length > 0 && (
            <div className="rounded-xl border border-emerald-900/40 bg-emerald-950/5 p-5 space-y-4 animate-slide-in">
              <div className="flex items-center justify-between border-b border-emerald-950 pb-3">
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-5 w-5 text-emerald-400" />
                  <h3 className="text-sm font-semibold text-emerald-300">Synthesized Project Ideas</h3>
                </div>
                <button
                  onClick={() => setGeneratedIdeas([])}
                  className="text-zinc-500 hover:text-zinc-300 transition"
                  title="Clear ideas"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-3.5">
                {generatedIdeas.map((idea, index) => (
                  <div
                    key={index}
                    className="flex gap-3 items-start bg-zinc-950/30 border border-zinc-900 rounded-lg p-4 text-zinc-300"
                  >
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-950 border border-emerald-800 text-[10px] font-bold text-emerald-400">
                      {index + 1}
                    </span>
                    <p className="text-xs leading-relaxed select-text">{idea}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

      </div>

      {/* Global Error toast banner */}
      {error && (
        <div className="rounded-lg border border-red-900/50 bg-red-900/10 px-4 py-3 flex items-center justify-between gap-3 shrink-0">
          <p className="text-xs text-red-300 select-text">{error}</p>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300" aria-label="Dismiss error">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Create Notebook Dialog */}
      <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-1.5">
              <BookOpen className="h-4.5 w-4.5 text-indigo-500" />
              Create Notebook
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateNotebook} className="space-y-3">
            <div>
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono mb-1.5 block">
                Title
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Quantum Algorithms Study"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="w-full rounded-lg border border-zinc-850 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 placeholder-zinc-600 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono mb-1.5 block">
                Description
              </label>
              <textarea
                placeholder="Summary of research themes, courses, or paper topics..."
                rows={3}
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                className="w-full rounded-lg border border-zinc-850 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 placeholder-zinc-650 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/50 resize-none font-sans"
              />
            </div>
          </form>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowCreateModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleCreateNotebook}
              disabled={isCreatingNb || !newTitle.trim()}
            >
              {isCreatingNb ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </div>
  );
}
