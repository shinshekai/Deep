"use client";

import { useState, useEffect, useRef, type ReactNode, type ComponentType } from "react";
import { Settings as SettingsIcon, Save, RefreshCw, Database, Cpu, Layers, HardDrive, Network, Sparkles, Brain, CheckCircle2, Loader2, Eye, EyeOff, Palette, Shield } from "lucide-react";
import { API_BASE_URL, secureFetch } from "@/lib/config";
import { getEpisodes, type MemoryEpisode } from "@/lib/memory";
import { useTheme } from "@/providers/theme-provider";
import { useT } from "@/lib/i18n";

const InputField = ({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  hint,
  fieldKey,
  isSecret = false,
}: {
  label: string;
  value: string | number;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  hint?: string;
  fieldKey?: string;
  isSecret?: boolean;
}) => {
  const [isRevealed, setIsRevealed] = useState(false);

  return (
    <div className="flex flex-col gap-1.5 font-sans">
      <label className="text-[10px] uppercase font-bold text-zinc-450 tracking-wider font-mono">{label}</label>
      <div className="relative">
        <input
          type={isSecret && !isRevealed ? "text" : type}
          value={isSecret && !isRevealed ? "\u2022".repeat(8) : value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={isSecret && !isRevealed ? undefined : placeholder}
          readOnly={isSecret && !isRevealed}
          aria-label={label}
          className={`rounded-lg border border-zinc-900 bg-zinc-950 px-3 py-2 text-xs text-zinc-150 placeholder-zinc-700 focus:outline-none focus:border-indigo-650 leading-relaxed font-sans${isSecret ? " pr-9" : ""}`}
          onFocus={() => {
            if (isSecret && !isRevealed) {
              setIsRevealed(true);
              if (fieldKey) onChange("");
            }
          }}
        />
        {isSecret && (
          <button
            type="button"
            tabIndex={-1}
            onClick={() => setIsRevealed((prev) => !prev)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition cursor-pointer"
            aria-label={isRevealed ? `Hide ${label}` : `Show ${label}`}
          >
            {isRevealed ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>
      {hint && <p className="text-[9px] font-mono text-zinc-400 leading-normal">{hint}</p>}
    </div>
  );
};

const ToggleField = ({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
  hint?: string;
}) => (
  <div className="flex items-center justify-between py-1 font-sans">
    <div className="space-y-0.5">
      <label className="text-[10px] uppercase font-bold text-zinc-450 tracking-wider font-mono">{label}</label>
      {hint && <p className="text-[9px] font-mono text-zinc-400 leading-normal">{hint}</p>}
    </div>
    <button
      onClick={() => onChange(!value)}
      aria-label={label}
      role="switch"
      aria-checked={value}
      className={`relative h-5 w-9 rounded-full transition-colors cursor-pointer focus:outline-none ${
        value ? "bg-indigo-600" : "bg-zinc-800"
      }`}
    >
      <span
        className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
          value ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  </div>
);

const SelectField = ({
  label,
  value,
  options,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
  hint?: string;
}) => (
  <div className="flex flex-col gap-1.5 font-sans">
    <label className="text-[10px] uppercase font-bold text-zinc-450 tracking-wider font-mono">{label}</label>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={label}
      className="rounded-lg border border-zinc-900 bg-zinc-950 px-3 py-2 text-xs text-zinc-150 focus:outline-none focus:border-indigo-650 cursor-pointer font-sans"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
    {hint && <p className="text-[9px] font-mono text-zinc-400 leading-normal">{hint}</p>}
  </div>
);

const Section = ({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: ComponentType<{ className?: string }>;
  children: ReactNode;
}) => (
  <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-5 space-y-4 shadow-inner">
    <h3 className="flex items-center gap-2 text-xs font-bold text-zinc-350 uppercase tracking-wider font-mono border-b border-zinc-900 pb-2">
      <Icon className="h-4 w-4 text-indigo-400" />
      {title}
    </h3>
    <div className="space-y-4">
      {children}
    </div>
  </div>
);

type Config = {
  // LM Studio
  llm_host: string;
  llm_port: number;
  llm_api_key: string;
  llm_model: string;

  // Embedding
  embedding_host: string;
  embedding_api_key: string;
  embedding_model: string;

  // TurboQuant
  turboquant_enabled: boolean;
  turboquant_bits: string;
  turboquant_resid: string;
  turboquant_tier: string;

  // VRAM
  vram_safety_margin: string;
  t2_ttl: string;
  t3_ttl: string;

  // Memory
  memory_enabled: boolean;
  memory_db_path: string;
  memory_max_episodes_recall: number;
  memory_max_facts_recall: number;
  memory_fact_confidence_threshold: number;
  memory_decay_rate: number;
  memory_extraction_model_tier: number;

  // System
  backend_port: string;
  frontend_port: string;
  search_provider: string;

  // LLM Behavior
  enable_thinking: boolean;
};

const DEFAULT_CONFIG: Config = {
  llm_host: "http://localhost",
  llm_port: 1234,
  llm_api_key: "lm-studio",
  llm_model: "",
  embedding_host: "http://localhost",
  embedding_api_key: "lm-studio",
  embedding_model: "",
  turboquant_enabled: true,
  turboquant_bits: "4",
  turboquant_resid: "256",
  turboquant_tier: "auto",
  vram_safety_margin: "15",
  t2_ttl: "600",
  t3_ttl: "300",
  memory_enabled: true,
  memory_db_path: "data/memory/deep_memory.db",
  memory_max_episodes_recall: 5,
  memory_max_facts_recall: 10,
  memory_fact_confidence_threshold: 0.2,
  memory_decay_rate: 0.1,
  memory_extraction_model_tier: 1,
  backend_port: "8001",
  frontend_port: "3782",
  search_provider: "none",
  enable_thinking: false,
};

export default function SettingsPage() {
  const [config, setConfig] = useState<Config>(DEFAULT_CONFIG);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const originalKeysRef = useRef<Record<string, string>>({});
  const [memoryHealthStatus, setMemoryHealthStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [memoryHealthMessage, setMemoryHealthMessage] = useState("");
  const [showMemoryHistory, setShowMemoryHistory] = useState(false);
  const [memoryEpisodes, setMemoryEpisodes] = useState<MemoryEpisode[]>([]);
  const [memoryEpisodesLoading, setMemoryEpisodesLoading] = useState(false);
  const { theme, setTheme, themes } = useTheme();
  const { t, locale, setLocale, locales } = useT();
  const [auditCatalog, setAuditCatalog] = useState<Record<string, string>>({});

  // Load current config from backend on mount
  useEffect(() => {
    secureFetch(`${API_BASE_URL}/config`)
      .then((res) => res.json())
      .then((data) => {
        setConfig((prev) => ({ ...prev, ...data }));
        originalKeysRef.current = {
          llm_api_key: data.llm_api_key || "",
          embedding_api_key: data.embedding_api_key || "",
        };
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    secureFetch(`${API_BASE_URL}/system/data/audit-stats`)
      .then(r => r.json())
      .then(d => setAuditCatalog(d.catalog || {}))
      .catch(() => {});
  }, []);

  const set = <K extends keyof Config>(key: K, value: Config[K]) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    const payload = { ...config };
    const bullets = "\u2022".repeat(8);
    if (payload.llm_api_key === bullets) {
      payload.llm_api_key = originalKeysRef.current.llm_api_key;
    }
    if (payload.embedding_api_key === bullets) {
      payload.embedding_api_key = originalKeysRef.current.embedding_api_key;
    }
    secureFetch(`${API_BASE_URL}/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(() => {
        setSaved(true);
        setTimeout(() => setSaved(false), 4000);
      })
      .catch(() => {});
  };

  const handleReset = () => {
    if (confirm("Are you sure you want to reset all configurations to standard local defaults?")) {
      setConfig(DEFAULT_CONFIG);
      setSaved(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 max-w-5xl mx-auto w-full select-none">
      
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-900 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <SettingsIcon className="h-6 w-6 text-indigo-500 animate-spin-slow" />
            {t("settings.title")}
          </h1>
          <p className="text-sm text-zinc-400 mt-1 font-sans">
            {t("settings.description")}
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleReset}
            disabled={loading}
            aria-label="Reset to defaults"
            className="flex items-center gap-1.5 rounded-lg border border-zinc-900 bg-zinc-950 px-4 py-2 text-xs font-semibold text-zinc-450 hover:border-zinc-800 hover:text-zinc-300 transition cursor-pointer disabled:opacity-40"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>{t("settings.reset")}</span>
          </button>
          <button
            onClick={handleSave}
            disabled={loading}
            aria-label="Save settings"
            className="flex items-center gap-1.5 rounded-lg bg-indigo-650 px-4.5 py-2 text-xs font-bold text-white hover:bg-indigo-500 transition cursor-pointer shadow-md shadow-indigo-600/10 disabled:opacity-40"
          >
            <Save className="h-3.5 w-3.5" />
            <span>{t("settings.save")}</span>
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-5 space-y-3 font-sans">
        <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono border-b border-zinc-900 pb-2">
          <Palette className="h-3.5 w-3.5 text-indigo-400" />
          <span>Theme</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {themes.map((t) => (
            <button
              key={t.id}
              onClick={() => setTheme(t.id)}
              aria-label={`Switch to ${t.label} theme`}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
                theme === t.id
                  ? "border-indigo-500 bg-indigo-600/20 text-indigo-300"
                  : "border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-5 space-y-3 font-sans">
        <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono border-b border-zinc-900 pb-2">
          <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
          <span>Language / 语言</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {locales.map((l) => (
            <button
              key={l.code}
              onClick={() => setLocale(l.code)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
                locale === l.code
                  ? "border-indigo-500 bg-indigo-600/20 text-indigo-300"
                  : "border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-5 space-y-3 font-sans">
        <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
          <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono">
            <Shield className="h-3.5 w-3.5 text-indigo-400" />
            <span>Audit Log</span>
          </div>
          <a
            href={`${API_BASE_URL}/system/data/audit-log?format=json`}
            target="_blank"
            rel="noopener"
            className="text-[9px] text-indigo-400 hover:text-indigo-300 font-mono"
          >
            Export JSON →
          </a>
        </div>
        <div className="text-[10px] text-zinc-500 font-mono">
          Structured audit events with SQLite persistence. Export as JSON or CSV.
          {Object.keys(auditCatalog).length > 0 && (
            <span className="text-indigo-400"> {Object.keys(auditCatalog).length} event types tracked.</span>
          )}
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border border-dashed border-zinc-900 p-12 text-center text-xs text-zinc-500 font-mono">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-400 mx-auto mb-3" />
          <span>Retrieving system configurations...</span>
        </div>
      ) : (
        <>
        <div className="grid gap-6 md:grid-cols-2 animate-slide-in select-text">
          
          {/* Column 1 */}
          <div className="space-y-6">
            
            {/* LM Studio Connection */}
            <Section title={t("settings.section.lm_studio")} icon={Database}>
              <InputField
                label="Base Url Host"
                value={config.llm_host}
                onChange={(v) => set("llm_host", v)}
                placeholder="http://localhost"
                hint="Default: http://localhost"
              />
              <InputField
                label="Port"
                type="number"
                value={config.llm_port}
                onChange={(v) => set("llm_port", Number(v))}
                hint="Uvicorn proxy routing port (Default: 1234)"
              />
              <InputField
                label="API Authorization Key"
                value={config.llm_api_key}
                onChange={(v) => set("llm_api_key", v)}
                hint="Authorization key details (Default: lm-studio)"
                fieldKey="llm_api_key"
                isSecret
              />
              <InputField
                label="Model Identifier"
                value={config.llm_model}
                onChange={(v) => set("llm_model", v)}
                placeholder="Qwen3-8B-Q4_K_M"
                hint="Primary resident LLM model ID loaded in VRAM"
              />
              <ToggleField
                label="Enable Thinking"
                value={config.enable_thinking}
                onChange={(v) => set("enable_thinking", v)}
                hint="Allow models to use chain-of-thought reasoning (increases latency + cost)"
              />
            </Section>

            {/* Embedding Model */}
            <Section title={t("settings.section.embedding")} icon={Network}>
              <InputField
                label="Base Url Host"
                value={config.embedding_host}
                onChange={(v) => set("embedding_host", v)}
                placeholder="http://localhost"
                hint="Default: http://localhost"
              />
              <InputField
                label="API Authorization Key"
                value={config.embedding_api_key}
                onChange={(v) => set("embedding_api_key", v)}
                hint="Authorization key details (Default: lm-studio)"
                fieldKey="embedding_api_key"
                isSecret
              />
              <InputField
                label="Model Identifier"
                value={config.embedding_model}
                onChange={(v) => set("embedding_model", v)}
                placeholder="text-embedding-qwen3-embedding-8b"
                hint="Model ID used specifically for vector embedding builds"
              />
            </Section>
          </div>

          {/* Column 2 */}
          <div className="space-y-6">
            
            {/* TurboQuant KV Cache */}
            <Section title={t("settings.section.turboquant")} icon={Cpu}>
              <ToggleField
                label="Quantization Enabled"
                value={config.turboquant_enabled}
                onChange={(v) => set("turboquant_enabled", v)}
                hint="Enable asymmetric cache quantization at startup"
              />
              <SelectField
                label="Bit Width Precision"
                value={config.turboquant_bits}
                options={[
                  { value: "3", label: "3-bit compression" },
                  { value: "4", label: "4-bit compression (optimal tradeoff)" },
                ]}
                onChange={(v) => set("turboquant_bits", v)}
                hint="Quantized bits representation"
              />
              <InputField
                label="FP16 Residual Window"
                type="number"
                value={config.turboquant_resid}
                onChange={(v) => set("turboquant_resid", v)}
                hint="Tokens count kept in full FP16 precision (128–256)"
              />
              <SelectField
                label="Integration Tier Mode"
                value={config.turboquant_tier}
                options={[
                  { value: "auto", label: "Auto-detect (recommended)" },
                  { value: "1", label: "Tier 1: LM Studio native GGUF" },
                  { value: "2", label: "Tier 2: turboquant-server proxy" },
                  { value: "3", label: "Tier 3: app-layer Python transformers" },
                ]}
                onChange={(v) => set("turboquant_tier", v)}
                hint="Hardware level auto-detection cascader"
              />
            </Section>

            {/* VRAM Pressure Management */}
            <Section title={t("settings.section.vram")} icon={HardDrive}>
              <InputField
                label="Safety Buffer Margin (%)"
                type="number"
                value={config.vram_safety_margin}
                onChange={(v) => set("vram_safety_margin", v)}
                hint="Projected margin reserved for unexpected allocations (Default: 15%)"
              />
              <InputField
                label="T2 Idle Timeout (Seconds)"
                type="number"
                value={config.t2_ttl}
                onChange={(v) => set("t2_ttl", v)}
                hint="TTL duration before semi-resident reasoning models unload (Default: 600s)"
              />
              <InputField
                label="T3 Idle Timeout (Seconds)"
                type="number"
                value={config.t3_ttl}
                onChange={(v) => set("t3_ttl", v)}
                hint="TTL duration before on-demand generation models unload (Default: 300s)"
              />
            </Section>

            {/* System Settings */}
            <Section title={t("settings.section.system")} icon={Layers}>
              <div className="grid grid-cols-2 gap-3">
                <InputField
                  label="Backend Port"
                  value={config.backend_port}
                  onChange={(v) => set("backend_port", v)}
                />
                <InputField
                  label="Frontend Port"
                  value={config.frontend_port}
                  onChange={(v) => set("frontend_port", v)}
                />
              </div>
              <SelectField
                label="Web Search Provider"
                value={config.search_provider}
                options={[
                  { value: "none", label: "None (Offline-only)" },
                  { value: "perplexity", label: "Perplexity API" },
                ]}
                onChange={(v) => set("search_provider", v)}
                hint="Enables online search cascades during deep research"
              />
            </Section>
          </div>
        </div>

        {/* Memory Config */}
        <div className="grid gap-6 md:grid-cols-2 animate-slide-in select-text">
          <div className="space-y-6">
            <Section title={t("settings.section.memory")} icon={Brain}>
              <ToggleField
                label="Memory Enabled"
                value={config.memory_enabled}
                onChange={(v) => set("memory_enabled", v)}
                hint="Enable episodic memory recall and fact storage"
              />
              <InputField
                label="Max Episodes Recall"
                type="number"
                value={config.memory_max_episodes_recall}
                onChange={(v) => set("memory_max_episodes_recall", Number(v))}
                hint="Maximum episodes returned per recall (Default: 5)"
              />
              <InputField
                label="Max Facts Recall"
                type="number"
                value={config.memory_max_facts_recall}
                onChange={(v) => set("memory_max_facts_recall", Number(v))}
                hint="Maximum facts returned per recall (Default: 10)"
              />
              <InputField
                label="Fact Confidence Threshold"
                type="number"
                value={config.memory_fact_confidence_threshold}
                onChange={(v) => set("memory_fact_confidence_threshold", Number(v))}
                hint="Minimum confidence to include facts (Default: 0.2)"
              />
              <InputField
                label="Decay Rate"
                type="number"
                value={config.memory_decay_rate}
                onChange={(v) => set("memory_decay_rate", Number(v))}
                hint="Decay factor applied to older episodes (Default: 0.1)"
              />
              <SelectField
                label="Extraction Model Tier"
                value={String(config.memory_extraction_model_tier)}
                options={[
                  { value: "1", label: "Tier 1: Low VRAM (fast extraction)" },
                  { value: "2", label: "Tier 2: High quality (slower)" },
                ]}
                onChange={(v) => set("memory_extraction_model_tier", Number(v))}
                hint="Model tier for fact extraction pipeline"
              />
              <InputField
                label="Database Path"
                value={config.memory_db_path}
                onChange={() => {}}
                hint="SQLite storage path (read-only)"
              />
              <div className="pt-1">
                <button
                  onClick={() => {
                    setMemoryHealthStatus("loading");
                    setMemoryHealthMessage("");
                    secureFetch(`${API_BASE_URL}/memory/health`)
                      .then((res) => {
                        if (res.ok) {
                          setMemoryHealthStatus("ok");
                          setMemoryHealthMessage("Memory service is healthy");
                        } else {
                          setMemoryHealthStatus("error");
                          setMemoryHealthMessage(`Status ${res.status}`);
                        }
                      })
                      .catch((e) => {
                        setMemoryHealthStatus("error");
                        setMemoryHealthMessage(e.message || "Connection failed");
                      });
                  }}
                  disabled={memoryHealthStatus === "loading"}
                  className="flex items-center gap-1.5 rounded-lg border border-zinc-900 bg-zinc-950 px-4 py-2 text-xs font-semibold text-zinc-450 hover:border-zinc-800 hover:text-zinc-300 transition cursor-pointer disabled:opacity-40"
                >
                  {memoryHealthStatus === "loading" ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Database className="h-3.5 w-3.5" />
                  )}
                   <span>{t("settings.test_memory")}</span>
                </button>
                {memoryHealthMessage && (
                  <p className={`text-[10px] font-mono mt-1.5 ${memoryHealthStatus === "ok" ? "text-emerald-400" : "text-red-400"}`}>
                    {memoryHealthMessage}
                  </p>
                )}
              </div>
            </Section>
          </div>

          <div className="space-y-6">
            <Section title={t("settings.section.memory_history")} icon={Sparkles}>
              <div className="flex items-center justify-between">
                <p className="text-[9px] font-mono text-zinc-400 leading-normal">
                  View recent episodes stored by the memory system.
                </p>
                <button
                  onClick={() => {
                    const next = !showMemoryHistory;
                    setShowMemoryHistory(next);
                    if (next && memoryEpisodes.length === 0) {
                      setMemoryEpisodesLoading(true);
                      getEpisodes("default", 10, 0)
                        .then((data) => {
                          setMemoryEpisodes(Array.isArray(data) ? data : data.episodes || []);
                        })
                        .catch(() => setMemoryEpisodes([]))
                        .finally(() => setMemoryEpisodesLoading(false));
                    }
                  }}
                  className="flex items-center gap-1.5 rounded-lg border border-zinc-900 bg-zinc-950 px-4 py-2 text-xs font-semibold text-zinc-450 hover:border-zinc-800 hover:text-zinc-300 transition cursor-pointer shrink-0"
                >
                  {showMemoryHistory ? "Hide" : "View Recent Activity"}
                </button>
              </div>
              {showMemoryHistory && (
                <div className="mt-3 rounded-lg border border-zinc-900 bg-zinc-950/60 overflow-hidden">
                  {memoryEpisodesLoading ? (
                    <div className="p-6 text-center">
                      <Loader2 className="h-4 w-4 animate-spin text-indigo-400 mx-auto mb-2" />
                      <p className="text-[10px] font-mono text-zinc-500">Loading episodes...</p>
                    </div>
                  ) : memoryEpisodes.length === 0 ? (
                    <div className="p-6 text-center text-[10px] font-mono text-zinc-500">
                      No episodes recorded yet.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-[10px] font-mono">
                        <thead>
                          <tr className="border-b border-zinc-900">
                            <th className="px-3 py-2 text-left text-zinc-400 font-semibold">Timestamp</th>
                            <th className="px-3 py-2 text-left text-zinc-400 font-semibold">Query</th>
                            <th className="px-3 py-2 text-left text-zinc-400 font-semibold">Session</th>
                            <th className="px-3 py-2 text-left text-zinc-400 font-semibold">Agents</th>
                          </tr>
                        </thead>
                        <tbody>
                          {memoryEpisodes.map((ep) => (
                            <tr key={ep.id} className="border-b border-zinc-900/50 last:border-0 hover:bg-zinc-900/20">
                              <td className="px-3 py-2 text-zinc-300 whitespace-nowrap">
                                {new Date(ep.created_at * 1000).toLocaleString()}
                              </td>
                              <td className="px-3 py-2 text-zinc-300 max-w-[200px] truncate" title={ep.query}>
                                {ep.query.length > 60 ? ep.query.slice(0, 60) + "..." : ep.query}
                              </td>
                              <td className="px-3 py-2 text-zinc-300">{ep.session_type}</td>
                              <td className="px-3 py-2 text-zinc-300">
                                {Array.isArray(ep.agents) ? ep.agents.join(", ") : "-"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </Section>
          </div>
        </div>
        </>
      )}

      {/* Save Success Toast Notifications */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 select-none pointer-events-none max-w-sm" role="status" aria-live="polite">
        {saved && (
          <div className="rounded-lg border border-emerald-950 bg-emerald-950/80 backdrop-blur-md px-4 py-3 text-xs text-emerald-400 flex items-center gap-2 pointer-events-auto shadow-lg shadow-emerald-950/20 animate-slide-in">
            <CheckCircle2 className="h-4.5 w-4.5 text-emerald-400 shrink-0" />
            <span>Successfully saved configurations directly to .env!</span>
          </div>
        )}
      </div>

    </div>
  );
}
