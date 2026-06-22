"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  DiscoveredModel,
  ModelDiscoveryResponse,
  ModelProvider,
} from "@/types/api";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import { toast } from "sonner";
import { Eye, EyeOff, Check, AlertCircle, ExternalLink } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { ModelsHeader } from "@/components/models/models-header";
import { ConnectionRail } from "@/components/models/connection-rail";
import { FilterToolbar } from "@/components/models/filter-toolbar";
import { TierSlotCard } from "@/components/models/tier-slot-card";
import { estimateVramNeeds } from "@/lib/estimate-vram";
import { useAppStore } from "@/stores";

const EMPTY_DISCOVERY: ModelDiscoveryResponse = {
  local: [],
  cloud: [],
  active_selection: null,
};

export default function ModelsConsoleV2() {
  const [discovery, setDiscovery] = useState<ModelDiscoveryResponse>(EMPTY_DISCOVERY);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState<string | null>(null);
  const setModelSelection = useAppStore((s) => s.setModelSelection);

  const [telemetry, setTelemetry] = useState({
    total_mb: 24576,
    used_mb: 8192,
    free_mb: 16384,
    utilization_pct: 33.3,
    pressure_level: "green",
    gpu_available: true,
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedParamCat, setSelectedParamCat] = useState<string>("all");

  // Provider setup drawer state
  const [activeSetupProvider, setActiveSetupProvider] = useState<ModelProvider | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [baseUrlInput, setBaseUrlInput] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; latency?: number; error?: string } | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);

  async function loadDiscovery() {
    setLoading(true);
    try {
      const response = await secureFetch(`${API_BASE_URL}/models/discover`);
      if (response.ok) {
        const data = (await response.json()) as ModelDiscoveryResponse;
        setDiscovery(data);
      }
    } catch (e) {
      console.error("Failed to load model discovery data", e);
      setDiscovery(EMPTY_DISCOVERY);
    } finally {
      setLoading(false);
    }
  }

  async function loadTelemetry() {
    try {
      const response = await secureFetch(`${API_BASE_URL}/vram/status`);
      if (response.ok) {
        const data = await response.json();
        setTelemetry(data);
      }
    } catch (e) {
      console.error("Failed to fetch VRAM telemetry", e);
    }
  }

  useEffect(() => {
    loadDiscovery();
    loadTelemetry();
    const interval = setInterval(loadTelemetry, 5000);
    return () => clearInterval(interval);
  }, []);

  const activeSelections = useMemo(() => {
    if (discovery.active_selections) {
      return discovery.active_selections;
    }
    return { T1: null, T2: null, T3: discovery.active_selection };
  }, [discovery]);

  const allAvailableModels = useMemo(() => {
    const list: DiscoveredModel[] = [];
    [...(discovery.local ?? []), ...(discovery.cloud ?? [])].forEach((prov) => {
      if (prov.status === "available") {
        prov.models.forEach((m) => list.push(m));
      }
    });
    return list;
  }, [discovery]);

  const t1EmbeddingModels = useMemo(() => {
    return allAvailableModels.filter((m) => {
      const isEmbed = m.metadata?.capabilities?.includes("embedding") || m.id.toLowerCase().includes("embed") || m.id.toLowerCase().includes("readerlm");
      const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.toLowerCase().includes(searchQuery.toLowerCase());
      return isEmbed && matchesSearch;
    });
  }, [allAvailableModels, searchQuery]);

  const t2ReasoningModels = useMemo(() => {
    return allAvailableModels.filter((m) => {
      const isReasoning = m.metadata?.capabilities?.includes("reasoning") || m.id.toLowerCase().includes("r1") || m.id.toLowerCase().includes("reason");
      const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesParam = selectedParamCat === "all" || m.metadata?.parameter_size_cat === selectedParamCat;
      return isReasoning && matchesSearch && matchesParam;
    });
  }, [allAvailableModels, searchQuery, selectedParamCat]);

  const t3GenerationModels = useMemo(() => {
    return allAvailableModels.filter((m) => {
      const isEmbeddingOnly = m.metadata?.capabilities?.includes("embedding") && !m.metadata?.capabilities?.includes("chat");
      const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesParam = selectedParamCat === "all" || m.metadata?.parameter_size_cat === selectedParamCat;
      return !isEmbeddingOnly && matchesSearch && matchesParam;
    });
  }, [allAvailableModels, searchQuery, selectedParamCat]);

  async function selectModelForTier(tier: "T1" | "T2" | "T3", model: DiscoveredModel) {
    const key = `${tier}:${model.provider_id}:${model.id}`;
    setSelecting(key);

    const est = estimateVramNeeds(model);
    const freeGb = telemetry.free_mb / 1024;
    const isLocal = model.source === "local";

    if (isLocal && est.totalGb > freeGb) {
      const warnProceed = window.confirm(
        `VRAM SAFETY WARNING:\n\n` +
        `This local model requires an estimated ${est.totalGb} GB memory (Weights: ${est.weightsGb} GB, KV Cache: ${est.kvCacheMb} MB).\n` +
        `Your GPU currently has only ${freeGb.toFixed(1)} GB of free VRAM remaining.\n\n` +
        `Loading this model may overload GPU memory and trigger automated orange/red cache evictions or runtime slow-downs.\n\n` +
        `Do you still want to target and load this model?`
      );
      if (!warnProceed) {
        setSelecting(null);
        return;
      }
    }

    try {
      const response = await secureFetch(`${API_BASE_URL}/models/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_type: model.source,
          provider_id: model.provider_id,
          model_id: model.id,
          tier,
          load: isLocal && model.provider_id === "lm_studio",
        }),
      });
      const data = await response.json();
      if (data.generation_supported) {
        toast.success(data.message || `Tier ${tier} pipeline target targeted successfully.`);
      } else {
        toast.info(data.message || `Tier ${tier} pipeline target targeted successfully.`);
      }
      setModelSelection(tier, { model_id: model.id, provider_id: model.provider_id, provider_type: model.source });
      await loadDiscovery();
      await loadTelemetry();
    } catch (e) {
      console.error(e);
      toast.error(`Failed to target route for Tier ${tier}.`);
    } finally {
      setSelecting(null);
    }
  }

  const openSetupDrawer = (provider: ModelProvider) => {
    setActiveSetupProvider(provider);
    setApiKeyInput("");
    setBaseUrlInput(provider.base_url ?? "");
    setShowApiKey(false);
    setTestResult(null);
    setTestingConnection(false);
    setSavingConfig(false);
  };

  const testProviderConnection = async () => {
    if (!activeSetupProvider) return;
    setTestingConnection(true);
    setTestResult(null);
    try {
      const response = await secureFetch(`${API_BASE_URL}/models/providers/${activeSetupProvider.id}/health`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKeyInput || undefined, base_url: baseUrlInput || undefined }),
      });
      const data = await response.json();
      if (response.ok && data.status === "available") {
        setTestResult({ status: "available", latency: data.latency_ms });
      } else {
        setTestResult({ status: data.status, error: data.error || "Connection test failed." });
      }
    } catch {
      setTestResult({ status: "unavailable", error: "Failed to connect to backend service." });
    } finally {
      setTestingConnection(false);
    }
  };

  const saveProviderConfig = async () => {
    if (!activeSetupProvider) return;
    setSavingConfig(true);
    try {
      const response = await secureFetch(`${API_BASE_URL}/models/providers/${activeSetupProvider.id}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKeyInput || undefined, base_url: baseUrlInput || undefined }),
      });
      const data = await response.json();
      if (response.ok && data.success) {
        toast.success(data.message);
        setActiveSetupProvider(null);
        await loadDiscovery();
      } else {
        setTestResult({ status: "unavailable", error: data.error || "Failed to save configuration." });
      }
    } catch {
      setTestResult({ status: "unavailable", error: "Network error occurred while saving." });
    } finally {
      setSavingConfig(false);
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col bg-zinc-950 text-zinc-100 antialiased">
      <ModelsHeader
        telemetry={telemetry}
        loading={loading}
        activeSelections={activeSelections}
        onRefresh={loadDiscovery}
      />

      <main className="flex flex-1 flex-col lg:flex-row gap-6 p-6">
        {loading ? (
          <div className="flex-1 space-y-6">
            <Skeleton className="h-8 w-48 rounded-lg" />
            <div className="grid gap-6 md:grid-cols-3">
              <Skeleton className="h-64 w-full rounded-xl" />
              <Skeleton className="h-64 w-full rounded-xl" />
              <Skeleton className="h-64 w-full rounded-xl" />
            </div>
          </div>
        ) : (
          <>
        <ConnectionRail
          localProviders={discovery.local ?? []}
          cloudProviders={discovery.cloud ?? []}
          onConfigure={openSetupDrawer}
        />

        <section className="w-full lg:w-[75%] flex flex-col gap-6">
          <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-6">
            <FilterToolbar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              selectedParamCat={selectedParamCat}
              onParamCatChange={setSelectedParamCat}
            />

            <div className="grid gap-6 md:grid-cols-3">
              <TierSlotCard
                tier="T1"
                slotLabel="RETRIEVAL SLOT"
                title="Embedding & Reader"
                description="Hierarchical indexing (PageIndex) and raw document parsing."
                activeSelection={activeSelections.T1}
                models={t1EmbeddingModels}
                selecting={selecting}
                onSelect={(m) => selectModelForTier("T1", m)}
                fallbackName="liquid/lfm2.5-1.2b default"
              />
              <TierSlotCard
                tier="T2"
                slotLabel="REASONING SLOT"
                title="Deep Thought & Rerank"
                description="Chain-of-thought routing, chunk evaluation, multi-hop reasoning."
                activeSelection={activeSelections.T2}
                models={t2ReasoningModels}
                selecting={selecting}
                onSelect={(m) => selectModelForTier("T2", m)}
                showVramEstimate
                fallbackName="deepseek-r1-8b default"
              />
              <TierSlotCard
                tier="T3"
                slotLabel="SYNTHESIS SLOT"
                title="Final Answer Generation"
                description="Formulates direct formatted solution synthesis with inline PageIndex page citations."
                activeSelection={activeSelections.T3}
                models={t3GenerationModels}
                selecting={selecting}
                onSelect={(m) => selectModelForTier("T3", m)}
                showVramEstimate
                fallbackName="gemma-4-12b default"
              />
            </div>
          </div>
        </section>
          </>
        )}
      </main>

      {/* Provider Setup Sheet */}
      <Sheet open={!!activeSetupProvider} onOpenChange={(v) => !v && setActiveSetupProvider(null)}>
        <SheetContent side="right" className="w-full sm:max-w-md p-6" showCloseButton={false}>
          {activeSetupProvider && (
            <>
              <SheetHeader className="p-0 mb-6">
                <div className="flex items-center justify-between border-b border-zinc-900 pb-4">
                  <SheetTitle className="text-base font-bold text-white uppercase tracking-wider font-sans">
                    Setup {activeSetupProvider.name}
                  </SheetTitle>
                </div>
              </SheetHeader>

              <div className="space-y-5">
                <div>
                  <label className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">Description</label>
                  <p className="text-xs text-zinc-400 mt-1 leading-normal bg-zinc-900/30 border border-zinc-900 rounded-lg p-3">
                    {activeSetupProvider.description}
                  </p>
                </div>

                {activeSetupProvider.setup_docs_url && (
                  <a
                    href={activeSetupProvider.setup_docs_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition"
                  >
                    <ExternalLink className="h-3.5 w-3.5 text-indigo-400" />
                    Acquire API Key or Access Setup Guide
                  </a>
                )}

                {activeSetupProvider.id !== "lm_studio" &&
                  activeSetupProvider.id !== "ollama" &&
                  activeSetupProvider.id !== "llama_cpp" &&
                  activeSetupProvider.id !== "vlm" && (
                    <div className="space-y-1.5">
                      <label className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">API Credential Key</label>
                      <div className="relative">
                        <input
                          type={showApiKey ? "text" : "password"}
                          value={apiKeyInput}
                          onChange={(e) => setApiKeyInput(e.target.value)}
                          placeholder="••••••••••••••••••••••••••••••••••••••••"
                          className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 py-2 pl-3.5 pr-10 text-xs text-white placeholder-zinc-700 focus:border-indigo-600 focus:outline-none transition font-mono"
                        />
                        <button
                          type="button"
                          onClick={() => setShowApiKey(!showApiKey)}
                          className="absolute inset-y-0 right-0 flex items-center pr-3 text-zinc-500 hover:text-zinc-300 focus:outline-none"
                          aria-label="Toggle API key visibility"
                        >
                          {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  )}

                {activeSetupProvider.id !== "lm_studio" && (
                  <div className="space-y-1.5">
                    <label className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">Endpoint Base URL</label>
                    <input
                      type="text"
                      value={baseUrlInput}
                      onChange={(e) => setBaseUrlInput(e.target.value)}
                      placeholder={activeSetupProvider.base_url || "http://localhost:port"}
                      className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 px-3.5 py-2 text-xs text-white placeholder-zinc-700 focus:border-indigo-600 focus:outline-none transition font-mono"
                    />
                  </div>
                )}

                {testResult && (
                  <div
                    className={`flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-xs ${
                      testResult.status === "available"
                        ? "border-emerald-800/40 bg-emerald-950/10 text-emerald-400"
                        : "border-rose-800/40 bg-rose-950/10 text-rose-400"
                    }`}
                  >
                    {testResult.status === "available" ? (
                      <>
                        <Check className="h-4.5 w-4.5 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold uppercase tracking-wider">Healthy Diagnostic:</span>
                          <div className="mt-1 font-mono text-[10px]">Connection Ping Latency: {testResult.latency} ms</div>
                        </div>
                      </>
                    ) : (
                      <>
                        <AlertCircle className="h-4.5 w-4.5 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold uppercase tracking-wider">Failed Connection:</span>
                          <div className="mt-1 text-zinc-300 leading-normal">{testResult.error}</div>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>

              <SheetFooter className="p-0 mt-6 border-t border-zinc-900 pt-5">
                <button
                  type="button"
                  disabled={testingConnection || savingConfig}
                  onClick={testProviderConnection}
                  className="flex items-center justify-center gap-1.5 h-10 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-850 text-xs font-semibold text-zinc-300 disabled:opacity-50 transition w-full"
                >
                  {testingConnection ? "Pinging Health check..." : "Run Active Health Diagnostics"}
                </button>
                <div className="flex gap-3 w-full">
                  <button
                    type="button"
                    onClick={() => setActiveSetupProvider(null)}
                    className="flex-1 h-10 rounded-lg border border-zinc-900 bg-zinc-950 text-xs font-semibold text-zinc-400 hover:text-white transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={savingConfig || testingConnection}
                    onClick={saveProviderConfig}
                    className="flex-1 h-10 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold text-white disabled:opacity-50 transition"
                  >
                    {savingConfig ? "Saving Config..." : "Save & Connect"}
                  </button>
                </div>
              </SheetFooter>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
