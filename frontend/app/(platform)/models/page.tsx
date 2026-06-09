"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import type {
  DiscoveredModel,
  ModelDiscoveryResponse,
  ModelProvider,
} from "@/types/api";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import {
  Key,
  Globe,
  Cpu,
  Check,
  AlertCircle,
  ExternalLink,
  Shield,
  Search,
  Activity,
  RefreshCw,
  Eye,
  EyeOff,
  Database,
  Cloud,
  Info,
  Server,
  Zap,
  Settings,
  X,
  Gauge,
  Layers,
  AlertTriangle,
} from "lucide-react";

const PROVIDER_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  lm_studio: Cpu,
  ollama: Database,
  llama_cpp: Server,
  vlm: Zap,
  openai: Globe,
  anthropic: Shield,
  gemini: Activity,
  mistral: Server,
  vertex: Cloud,
  openrouter: Globe,
  opencode: Key,
};

const EMPTY_DISCOVERY: ModelDiscoveryResponse = {
  local: [],
  cloud: [],
  active_selection: null,
};

// VRAM footprint estimator based on heuristics
function estimateVramNeeds(model: DiscoveredModel): { weightsGb: number; kvCacheMb: number; totalGb: number } {
  const id = model.id.toLowerCase();
  
  // Extract parameter size (e.g. 8b, 35b, 1.2b)
  let params = 8; // default fallback
  const paramMatch = id.match(/(\d+(?:\.\d+)?)[b]/);
  if (paramMatch) {
    params = parseFloat(paramMatch[1]);
  } else if (id.includes("1.2b")) {
    params = 1.2;
  } else if (id.includes("4b")) {
    params = 4;
  } else if (id.includes("35b")) {
    params = 35;
  } else if (id.includes("26b")) {
    params = 26;
  }
  
  // Quantization estimate: assume Q4/Q5 (~0.6 GB per B-parameter)
  let weightsGb = params * 0.65;
  if (id.includes("f16") || id.includes("fp16")) {
    weightsGb = params * 2.0;
  } else if (id.includes("q8") || id.includes("8-bit")) {
    weightsGb = params * 1.0;
  }
  
  // KV Cache context length estimate
  let context = 8192; // default
  if (model.metadata?.context_length) {
    context = typeof model.metadata.context_length === "number" 
      ? model.metadata.context_length 
      : parseInt(model.metadata.context_length) || 8192;
  }
  
  // Estimate KV cache size (roughly 0.05 MB per token per billion parameters)
  const kvCacheMb = (context * params * 0.05);
  const totalGb = weightsGb + (kvCacheMb / 1024);
  
  return {
    weightsGb: parseFloat(weightsGb.toFixed(1)),
    kvCacheMb: Math.round(kvCacheMb),
    totalGb: parseFloat(totalGb.toFixed(1)),
  };
}

export default function ModelsConsoleV2() {
  const [discovery, setDiscovery] = useState<ModelDiscoveryResponse>(EMPTY_DISCOVERY);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);

  // VRAM Real-Time Telemetry
  const [telemetry, setTelemetry] = useState({
    total_mb: 24576,
    used_mb: 8192,
    free_mb: 16384,
    utilization_pct: 33.3,
    pressure_level: "green",
    gpu_available: true,
  });

  // Setup Drawer state
  const [activeSetupProvider, setActiveSetupProvider] = useState<ModelProvider | null>(null);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [baseUrlInput, setBaseUrlInput] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; latency?: number; error?: string } | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedParamCat, setSelectedParamCat] = useState<string>("all");

  // Load models & selections
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

  // Load telemetry
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
    
    // Telemetry pooling
    const interval = setInterval(loadTelemetry, 5000);
    return () => clearInterval(interval);
  }, []);

  // Map out T1, T2, T3 active selections securely
  const activeSelections = useMemo(() => {
    if (discovery.active_selections) {
      return discovery.active_selections;
    }
    return {
      T1: null,
      T2: null,
      T3: discovery.active_selection,
    };
  }, [discovery]);

  // Flattened online models list
  const allAvailableModels = useMemo(() => {
    const list: DiscoveredModel[] = [];
    [...(discovery.local ?? []), ...(discovery.cloud ?? [])].forEach((prov) => {
      if (prov.status === "available") {
        prov.models.forEach((m) => {
          list.push(m);
        });
      }
    });
    return list;
  }, [discovery]);

  // Filtered lists per tier based on capabilities
  const t1EmbeddingModels = useMemo(() => {
    return allAvailableModels.filter(m => {
      const isEmbed = m.metadata?.capabilities?.includes("embedding") || m.id.toLowerCase().includes("embed") || m.id.toLowerCase().includes("readerlm");
      const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.toLowerCase().includes(searchQuery.toLowerCase());
      return isEmbed && matchesSearch;
    });
  }, [allAvailableModels, searchQuery]);

  const t2ReasoningModels = useMemo(() => {
    return allAvailableModels.filter(m => {
      const isReasoning = m.metadata?.capabilities?.includes("reasoning") || m.id.toLowerCase().includes("r1") || m.id.toLowerCase().includes("reason");
      const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesParam = selectedParamCat === "all" || m.metadata?.parameter_size_cat === selectedParamCat;
      return isReasoning && matchesSearch && matchesParam;
    });
  }, [allAvailableModels, searchQuery, selectedParamCat]);

  const t3GenerationModels = useMemo(() => {
    return allAvailableModels.filter(m => {
      const isEmbeddingOnly = m.metadata?.capabilities?.includes("embedding") && !m.metadata?.capabilities?.includes("chat");
      const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesParam = selectedParamCat === "all" || m.metadata?.parameter_size_cat === selectedParamCat;
      return !isEmbeddingOnly && matchesSearch && matchesParam;
    });
  }, [allAvailableModels, searchQuery, selectedParamCat]);

  // Select Model Route Handler
  async function selectModelForTier(tier: "T1" | "T2" | "T3", model: DiscoveredModel) {
    const key = `${tier}:${model.provider_id}:${model.id}`;
    setSelecting(key);
    setMessage(null);
    
    // VRAM warning check
    const est = estimateVramNeeds(model);
    const freeGb = telemetry.free_mb / 1024;
    const isLocal = model.source === "local";
    
    if (isLocal && est.totalGb > freeGb) {
      const warnProceed = window.confirm(
        `⚠️ VRAM SAFETY WARNING:\n\n` +
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
          tier: tier,
          load: isLocal && model.provider_id === "lm_studio",
        }),
      });
      const data = await response.json();
      setMessage({
        text: data.message || `Tier ${tier} pipeline target targeted successfully.`,
        type: data.generation_supported ? "success" : "info",
      });
      await loadDiscovery();
      await loadTelemetry();
    } catch (e) {
      console.error(e);
      setMessage({ text: `Failed to target route for Tier ${tier}.`, type: "error" });
    } finally {
      setSelecting(null);
    }
  }

  // Open config drawer
  const openSetupDrawer = (provider: ModelProvider) => {
    setActiveSetupProvider(provider);
    setApiKeyInput("");
    setBaseUrlInput(provider.base_url ?? "");
    setShowApiKey(false);
    setTestResult(null);
    setTestingConnection(false);
    setSavingConfig(false);
  };

  // Run connection test
  const testProviderConnection = async () => {
    if (!activeSetupProvider) return;
    setTestingConnection(true);
    setTestResult(null);
    try {
      const response = await secureFetch(`${API_BASE_URL}/models/providers/${activeSetupProvider.id}/health`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKeyInput || undefined,
          base_url: baseUrlInput || undefined,
        }),
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

  // Save config
  const saveProviderConfig = async () => {
    if (!activeSetupProvider) return;
    setSavingConfig(true);
    try {
      const response = await secureFetch(`${API_BASE_URL}/models/providers/${activeSetupProvider.id}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKeyInput || undefined,
          base_url: baseUrlInput || undefined,
        }),
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setMessage({ text: data.message, type: "success" });
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
      
      {/* ── STICKY OPERATIONAL HEADER ── */}
      <header className="sticky top-0 z-40 border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-md px-6 py-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white uppercase font-sans">Models Console</h1>
              <Badge className="bg-indigo-600/10 text-indigo-400 border-indigo-900/30 text-[10px] uppercase tracking-wider font-mono">v2.0</Badge>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Dual-loop multi-agent orchestration console for the DEEP local document pipeline.
            </p>
          </div>

          {/* Real-time Hardware Telemetry Bar */}
          <div className="flex flex-wrap items-center gap-4 bg-zinc-900/50 border border-zinc-850 rounded-lg px-4 py-2.5">
            <div className="flex items-center gap-2">
              <Gauge className="h-4 w-4 text-zinc-400" />
              <span className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">GPU Memory:</span>
            </div>

            {/* VRAM Progress bar */}
            <div className="flex items-center gap-3">
              <div className="relative h-2 w-32 rounded-full bg-zinc-800 overflow-hidden">
                <div 
                  className={`absolute h-full rounded-full transition-all duration-500 ${
                    telemetry.pressure_level === "red" 
                      ? "bg-red-500" 
                      : telemetry.pressure_level === "orange" 
                        ? "bg-orange-500" 
                        : telemetry.pressure_level === "yellow" 
                          ? "bg-yellow-500" 
                          : "bg-emerald-500"
                  }`}
                  style={{ width: `${telemetry.utilization_pct}%` }}
                />
              </div>
              <span className="text-xs font-semibold font-mono text-zinc-200">
                {Math.round(telemetry.used_mb / 1024)} / {Math.round(telemetry.total_mb / 1024)} GB
              </span>
              <span className="text-[10px] font-mono text-zinc-400">({Math.round(telemetry.utilization_pct)}%)</span>
            </div>

            <div className="h-4 w-[1px] bg-zinc-800" />

            {/* VRAM Pressure LED bulb */}
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  telemetry.pressure_level === "red" 
                    ? "bg-red-400" 
                    : telemetry.pressure_level === "orange" 
                      ? "bg-orange-400" 
                      : telemetry.pressure_level === "yellow" 
                        ? "bg-yellow-400" 
                        : "bg-emerald-400"
                }`} />
                <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                  telemetry.pressure_level === "red" 
                    ? "bg-red-500" 
                    : telemetry.pressure_level === "orange" 
                      ? "bg-orange-500" 
                      : telemetry.pressure_level === "yellow" 
                        ? "bg-yellow-500" 
                        : "bg-emerald-500"
                }`} />
              </span>
              <span className="text-xs uppercase font-bold text-zinc-300 tracking-wide font-mono">
                {telemetry.pressure_level}
              </span>
            </div>

            <button
              type="button"
              disabled={loading}
              onClick={loadDiscovery}
              className="flex h-7 w-7 items-center justify-center rounded border border-zinc-800 hover:border-zinc-700 bg-zinc-950 text-zinc-400 hover:text-white transition focus:outline-none"
              title="Refresh models index"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Dynamic active pipeline status bar inside header */}
        <div className="mt-4 flex flex-wrap gap-3 items-center text-xs bg-indigo-950/10 border-t border-zinc-900 pt-3">
          <span className="flex items-center gap-1 text-[10px] uppercase font-mono text-zinc-500 tracking-wider font-bold">
            <Layers className="h-3 w-3 text-indigo-400" /> Active Routes:
          </span>
          <span className="flex items-center gap-1 text-zinc-300">
            <span className="text-[10px] font-bold text-indigo-400 font-mono">T1</span>
            <span className="font-semibold text-zinc-200">
              {activeSelections.T1 ? activeSelections.T1.model_id : "Safe Fallback Cascade"}
            </span>
          </span>
          <span className="text-zinc-600">/</span>
          <span className="flex items-center gap-1 text-zinc-300">
            <span className="text-[10px] font-bold text-indigo-400 font-mono">T2</span>
            <span className="font-semibold text-zinc-200">
              {activeSelections.T2 ? activeSelections.T2.model_id : "Safe Fallback Cascade"}
            </span>
          </span>
          <span className="text-zinc-600">/</span>
          <span className="flex items-center gap-1 text-zinc-300">
            <span className="text-[10px] font-bold text-indigo-400 font-mono">T3</span>
            <span className="font-semibold text-zinc-200">
              {activeSelections.T3 ? activeSelections.T3.model_id : "Safe Fallback Cascade"}
            </span>
          </span>
        </div>
      </header>

      {/* Global Toast Messages */}
      {message && (
        <div className="mx-6 mt-4">
          <div
            className={`flex items-start gap-3 rounded-lg border px-4 py-3.5 text-sm transition-all duration-300 ${
              message.type === "success"
                ? "border-emerald-800/40 bg-emerald-950/10 text-emerald-300"
                : message.type === "error"
                  ? "border-rose-800/40 bg-rose-950/10 text-rose-300"
                  : "border-zinc-800 bg-zinc-900/50 text-zinc-300"
            }`}
          >
            {message.type === "error" ? (
              <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
            ) : message.type === "success" ? (
              <Check className="h-5 w-5 shrink-0 text-emerald-400" />
            ) : (
              <Info className="h-5 w-5 shrink-0 text-zinc-400" />
            )}
            <div className="grow font-medium">{message.text}</div>
            <button
              type="button"
              onClick={() => setMessage(null)}
              className="text-xs text-zinc-500 hover:text-zinc-300 font-mono uppercase"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ── TWO-COLUMN MAIN WORKSPACE ── */}
      <main className="flex flex-1 flex-col lg:flex-row gap-6 p-6">
        
        {/* LEFT CONNECTION RAIL (Width 25%) */}
        <section className="w-full lg:w-[25%] flex flex-col gap-6">
          <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-5">
            <div className="flex items-center justify-between border-b border-zinc-900 pb-3 mb-4">
              <span className="text-xs uppercase font-bold text-zinc-400 tracking-wider font-mono">Connection Rail</span>
              <span className="text-[10px] text-zinc-500">Local & Cloud Providers</span>
            </div>

            {/* Local Providers */}
            <div className="space-y-3 mb-6">
              <div className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider mb-2">Local Runtimes</div>
              {discovery.local?.map((provider) => {
                const Icon = PROVIDER_ICONS[provider.id] || Cpu;
                const active = provider.status === "available";
                return (
                  <div 
                    key={provider.id} 
                    className="flex items-center justify-between group rounded-lg border border-zinc-900 hover:border-zinc-800 bg-zinc-950/20 px-3.5 py-2.5 transition"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="relative flex h-2 w-2 shrink-0">
                        <span className={`relative inline-flex rounded-full h-2 w-2 ${active ? "bg-emerald-500" : "bg-zinc-700"}`} />
                      </span>
                      <Icon className="h-4 w-4 text-zinc-400 shrink-0" />
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-zinc-200 truncate">{provider.name}</div>
                        <div className="text-[9px] font-mono text-zinc-500 truncate">
                          {provider.base_url || "Inactive"}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => openSetupDrawer(provider)}
                      className="p-1 rounded text-zinc-500 hover:text-white hover:bg-zinc-900 transition focus:outline-none"
                      title={`Configure ${provider.name}`}
                    >
                      <Settings className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>

            {/* Cloud Providers */}
            <div className="space-y-3">
              <div className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider mb-2">Cloud Provider APIs</div>
              {discovery.cloud?.map((provider) => {
                const Icon = PROVIDER_ICONS[provider.id] || Cpu;
                const active = provider.status === "available";
                return (
                  <div 
                    key={provider.id} 
                    className="flex items-center justify-between group rounded-lg border border-zinc-900 hover:border-zinc-800 bg-zinc-950/20 px-3.5 py-2.5 transition"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <span className="relative flex h-2 w-2 shrink-0">
                        <span className={`relative inline-flex rounded-full h-2 w-2 ${active ? "bg-emerald-500" : "bg-zinc-750"}`} />
                      </span>
                      <Icon className="h-4 w-4 text-zinc-400 shrink-0" />
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-zinc-200 truncate">{provider.name}</div>
                        <div className="text-[9px] font-mono text-zinc-500 truncate">
                          {active ? "Connected" : "No API key"}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => openSetupDrawer(provider)}
                      className="p-1 rounded text-zinc-500 hover:text-white hover:bg-zinc-900 transition focus:outline-none"
                      title={`Configure ${provider.name}`}
                    >
                      <Settings className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* CENTER WORKSPACE (Width 75%) */}
        <section className="w-full lg:w-[75%] flex flex-col gap-6">
          <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-6">
            
            {/* Filter Toolbar */}
            <div className="flex flex-col gap-4 border-b border-zinc-900 pb-5 mb-6 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-bold text-white uppercase tracking-wide font-sans">Pipeline Routing Workspace</h2>
                <p className="text-xs text-zinc-400">Target models specifically to the T1, T2, or T3 pipeline slots.</p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <div className="relative">
                  <Search className="absolute inset-y-0 left-0 ml-2.5 h-3.5 w-3.5 text-zinc-500 self-center" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search models..."
                    aria-label="Search models"
                    className="h-8 rounded-lg border border-zinc-800 bg-zinc-950 pl-8 pr-3 text-xs text-white placeholder-zinc-600 focus:border-indigo-600 focus:outline-none transition w-44"
                  />
                </div>

                <select
                  value={selectedParamCat}
                  onChange={(e) => setSelectedParamCat(e.target.value)}
                  className="h-8 rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 text-xs text-zinc-300 focus:outline-none font-mono"
                >
                  <option value="all">ALL SIZES</option>
                  <option value="small">SMALL (&lt;7B)</option>
                  <option value="medium">MEDIUM (7B-32B)</option>
                  <option value="large">LARGE (&gt;32B)</option>
                </select>
              </div>
            </div>

            {/* THREE-TIER PIPELINES WORKSPACE SLOT CARDS */}
            <div className="grid gap-6 md:grid-cols-3">
              
              {/* T1 PIPELINE - RETRIEVAL (EMBEDDING) */}
              <div className="flex flex-col rounded-xl border border-zinc-900 bg-zinc-950/60 overflow-hidden">
                <div className="bg-indigo-950/10 border-b border-zinc-900 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold font-mono text-indigo-400 uppercase tracking-widest bg-indigo-950/40 border border-indigo-900/30 px-1.5 py-0.5 rounded">T1</span>
                    <span className="text-[10px] font-semibold text-zinc-500">RETRIEVAL SLOT</span>
                  </div>
                  <h3 className="text-sm font-bold text-zinc-200 mt-2">Embedding &amp; Reader</h3>
                  <p className="text-[11px] text-zinc-400 mt-1 leading-normal">
                    Hierarchical indexing (PageIndex) and raw document parsing.
                  </p>
                </div>

                {/* Active selection info */}
                <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 grow">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 font-mono tracking-wider">Active Route:</span>
                  {activeSelections.T1 ? (
                    <div className="mt-2.5 flex items-start gap-2 bg-emerald-950/5 border border-emerald-900/20 rounded p-2 text-xs">
                      <Check className="h-4.5 w-4.5 text-emerald-400 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <div className="font-semibold text-zinc-200 break-all">{activeSelections.T1.model_id}</div>
                        <div className="text-[9px] font-mono text-zinc-400 mt-0.5 uppercase tracking-wider">{activeSelections.T1.provider_id}</div>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-2.5 flex items-start gap-2 bg-yellow-950/5 border border-yellow-900/20 rounded p-2 text-xs">
                      <AlertTriangle className="h-4.5 w-4.5 text-yellow-500 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <div className="font-semibold text-yellow-400">Safe Fallback Cascade</div>
                        <div className="text-[9px] text-zinc-400 mt-0.5"> liquid/lfm2.5-1.2b default</div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Inline Models Selector list */}
                <div className="p-4 flex flex-col gap-2 max-h-[300px] overflow-y-auto">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 font-mono tracking-wider">Discovered Targets:</span>
                  {t1EmbeddingModels.length === 0 ? (
                    <div className="text-[11px] text-zinc-500 text-center py-6">No matching embedding models configured.</div>
                  ) : (
                    t1EmbeddingModels.map((model) => {
                      const isActive = activeSelections.T1?.model_id === model.id && activeSelections.T1?.provider_id === model.provider_id;
                      return (
                        <button
                          key={model.id}
                          onClick={() => selectModelForTier("T1", model)}
                          disabled={isActive || Boolean(selecting)}
                          className={`flex flex-col text-left p-2.5 rounded-lg border transition ${
                            isActive 
                              ? "bg-emerald-950/10 border-emerald-900/30 text-emerald-300"
                              : "bg-zinc-950 border-zinc-900 hover:border-zinc-800 text-zinc-300"
                          }`}
                        >
                          <div className="font-semibold text-xs break-all">{model.name}</div>
                          <div className="flex justify-between items-center w-full mt-1">
                            <span className="text-[9px] font-mono text-zinc-500 uppercase">{model.provider_id}</span>
                            {isActive && <span className="text-[9px] text-emerald-400 font-semibold font-mono uppercase tracking-wider">ACTIVE</span>}
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>

              {/* T2 PIPELINE - REASONING (SEMI-RESIDENT) */}
              <div className="flex flex-col rounded-xl border border-zinc-900 bg-zinc-950/60 overflow-hidden">
                <div className="bg-indigo-950/10 border-b border-zinc-900 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold font-mono text-indigo-400 uppercase tracking-widest bg-indigo-950/40 border border-indigo-900/30 px-1.5 py-0.5 rounded">T2</span>
                    <span className="text-[10px] font-semibold text-zinc-500">REASONING SLOT</span>
                  </div>
                  <h3 className="text-sm font-bold text-zinc-200 mt-2">Deep Thought &amp; Rerank</h3>
                  <p className="text-[11px] text-zinc-400 mt-1 leading-normal">
                    Chain-of-thought routing, chunk evaluation, multi-hop reasoning.
                  </p>
                </div>

                {/* Active selection info */}
                <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 grow">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 font-mono tracking-wider">Active Route:</span>
                  {activeSelections.T2 ? (
                    <div className="mt-2.5 flex items-start gap-2 bg-emerald-950/5 border border-emerald-900/20 rounded p-2 text-xs">
                      <Check className="h-4.5 w-4.5 text-emerald-400 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <div className="font-semibold text-zinc-200 break-all">{activeSelections.T2.model_id}</div>
                        <div className="text-[9px] font-mono text-zinc-400 mt-0.5 uppercase tracking-wider">{activeSelections.T2.provider_id}</div>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-2.5 flex items-start gap-2 bg-yellow-950/5 border border-yellow-900/20 rounded p-2 text-xs">
                      <AlertTriangle className="h-4.5 w-4.5 text-yellow-500 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <div className="font-semibold text-yellow-400">Safe Fallback Cascade</div>
                        <div className="text-[9px] text-zinc-400 mt-0.5">deepseek-r1-8b default</div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Inline Models Selector list */}
                <div className="p-4 flex flex-col gap-2 max-h-[300px] overflow-y-auto">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 font-mono tracking-wider">Discovered Targets:</span>
                  {t2ReasoningModels.length === 0 ? (
                    <div className="text-[11px] text-zinc-500 text-center py-6">No matching reasoning models configured.</div>
                  ) : (
                    t2ReasoningModels.map((model) => {
                      const isActive = activeSelections.T2?.model_id === model.id && activeSelections.T2?.provider_id === model.provider_id;
                      const est = estimateVramNeeds(model);
                      return (
                        <button
                          key={model.id}
                          onClick={() => selectModelForTier("T2", model)}
                          disabled={isActive || Boolean(selecting)}
                          className={`flex flex-col text-left p-2.5 rounded-lg border transition ${
                            isActive 
                              ? "bg-emerald-950/10 border-emerald-900/30 text-emerald-300"
                              : "bg-zinc-950 border-zinc-900 hover:border-zinc-800 text-zinc-300"
                          }`}
                        >
                          <div className="font-semibold text-xs break-all">{model.name}</div>
                          <div className="flex justify-between items-center w-full mt-1.5">
                            <span className="text-[9px] font-mono text-zinc-500 uppercase">{model.provider_id}</span>
                            <Badge className="bg-zinc-900 text-zinc-400 border-zinc-850 px-1 py-0 text-[8px]">{est.totalGb} GB est</Badge>
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>

              {/* T3 PIPELINE - SYNTHESIS (ON-DEMAND) */}
              <div className="flex flex-col rounded-xl border border-zinc-900 bg-zinc-950/60 overflow-hidden">
                <div className="bg-indigo-950/10 border-b border-zinc-900 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold font-mono text-indigo-400 uppercase tracking-widest bg-indigo-950/40 border border-indigo-900/30 px-1.5 py-0.5 rounded">T3</span>
                    <span className="text-[10px] font-semibold text-zinc-500">SYNTHESIS SLOT</span>
                  </div>
                  <h3 className="text-sm font-bold text-zinc-200 mt-2">Final Answer Generation</h3>
                  <p className="text-[11px] text-zinc-400 mt-1 leading-normal">
                    Formulates direct formatted solution synthesis with inline PageIndex page citations.
                  </p>
                </div>

                {/* Active selection info */}
                <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 grow">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 font-mono tracking-wider">Active Route:</span>
                  {activeSelections.T3 ? (
                    <div className="mt-2.5 flex items-start gap-2 bg-emerald-950/5 border border-emerald-900/20 rounded p-2 text-xs">
                      <Check className="h-4.5 w-4.5 text-emerald-400 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <div className="font-semibold text-zinc-200 break-all">{activeSelections.T3.model_id}</div>
                        <div className="text-[9px] font-mono text-zinc-400 mt-0.5 uppercase tracking-wider">{activeSelections.T3.provider_id}</div>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-2.5 flex items-start gap-2 bg-yellow-950/5 border border-yellow-900/20 rounded p-2 text-xs">
                      <AlertTriangle className="h-4.5 w-4.5 text-yellow-500 shrink-0 mt-0.5" />
                      <div className="min-w-0">
                        <div className="font-semibold text-yellow-400">Safe Fallback Cascade</div>
                        <div className="text-[9px] text-zinc-400 mt-0.5">gemma-4-12b default</div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Inline Models Selector list */}
                <div className="p-4 flex flex-col gap-2 max-h-[300px] overflow-y-auto">
                  <span className="text-[9px] uppercase font-bold text-zinc-500 font-mono tracking-wider">Discovered Targets:</span>
                  {t3GenerationModels.length === 0 ? (
                    <div className="text-[11px] text-zinc-500 text-center py-6">No matching synthesis models configured.</div>
                  ) : (
                    t3GenerationModels.map((model) => {
                      const isActive = activeSelections.T3?.model_id === model.id && activeSelections.T3?.provider_id === model.provider_id;
                      const est = estimateVramNeeds(model);
                      return (
                        <button
                          key={model.id}
                          onClick={() => selectModelForTier("T3", model)}
                          disabled={isActive || Boolean(selecting)}
                          className={`flex flex-col text-left p-2.5 rounded-lg border transition ${
                            isActive 
                              ? "bg-emerald-950/10 border-emerald-900/30 text-emerald-300"
                              : "bg-zinc-950 border-zinc-900 hover:border-zinc-800 text-zinc-300"
                          }`}
                        >
                          <div className="font-semibold text-xs break-all">{model.name}</div>
                          <div className="flex justify-between items-center w-full mt-1.5">
                            <span className="text-[9px] font-mono text-zinc-500 uppercase">{model.provider_id}</span>
                            <Badge className="bg-zinc-900 text-zinc-400 border-zinc-850 px-1 py-0 text-[8px]">{est.totalGb} GB est</Badge>
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>

            </div>
          </div>
        </section>
      </main>

      {/* ── RIGHT SLIDE-OUT SETUP DRAWER (CREDENTIALS) ── */}
      {activeSetupProvider && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-sm transition-all duration-300">
          
          {/* Drawer Panel container */}
          <div className="h-full w-full max-w-md border-l border-zinc-850 bg-zinc-950 p-6 shadow-2xl flex flex-col justify-between animate-slide-in relative">
            
            {/* Header */}
            <div>
              <div className="flex items-center justify-between border-b border-zinc-900 pb-4 mb-6">
                <div className="flex items-center gap-2">
                  {(() => {
                    const Icon = PROVIDER_ICONS[activeSetupProvider.id] || Cpu;
                    return <Icon className="h-5 w-5 text-indigo-400" />;
                  })()}
                  <h3 className="text-base font-bold text-white uppercase tracking-wider font-sans">Setup {activeSetupProvider.name}</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveSetupProvider(null)}
                  className="p-1 rounded text-zinc-400 hover:text-white hover:bg-zinc-900 transition focus:outline-none"
                  aria-label="Close provider setup drawer"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Form Content */}
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

                {/* API Key field (for cloud providers) */}
                {activeSetupProvider.id !== "lm_studio" &&
                  activeSetupProvider.id !== "ollama" &&
                  activeSetupProvider.id !== "llama_cpp" &&
                  activeSetupProvider.id !== "vlm" && (
                    <div className="space-y-1.5">
                      <label className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                        API Credential Key
                      </label>
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
                          aria-expanded={showApiKey}
                        >
                          {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                  )}

                {/* Endpoint URL configuration (for local or customizable providers) */}
                {activeSetupProvider.id !== "lm_studio" && (
                  <div className="space-y-1.5">
                    <label className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider">
                      Endpoint Base URL
                    </label>
                    <input
                      type="text"
                      value={baseUrlInput}
                      onChange={(e) => setBaseUrlInput(e.target.value)}
                      placeholder={activeSetupProvider.base_url || "http://localhost:port"}
                      className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 px-3.5 py-2 text-xs text-white placeholder-zinc-700 focus:border-indigo-600 focus:outline-none transition font-mono"
                    />
                  </div>
                )}

                {/* Active Diagnostic results */}
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
                          <div className="mt-1 font-mono text-[10px]">
                            Connection Ping Latency: {testResult.latency} ms
                          </div>
                        </div>
                      </>
                    ) : (
                      <>
                        <AlertCircle className="h-4.5 w-4.5 shrink-0 mt-0.5" />
                        <div>
                          <span className="font-bold uppercase tracking-wider">Failed Connection:</span>
                          <div className="mt-1 text-zinc-300 leading-normal">
                            {testResult.error}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Action Buttons Footer */}
            <div className="border-t border-zinc-900 pt-5 mt-6 flex flex-col gap-2.5">
              <button
                type="button"
                disabled={testingConnection || savingConfig}
                onClick={testProviderConnection}
                className="flex items-center justify-center gap-1.5 h-10 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-850 text-xs font-semibold text-zinc-300 disabled:opacity-50 transition"
              >
                {testingConnection ? "Pinging Health check..." : "Run Active Health Diagnostics"}
              </button>
              
              <div className="flex gap-3">
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
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
