"use client";

import { useState } from "react";
import { Settings as SettingsIcon, Save, RefreshCw, Database } from "lucide-react";

const API_BASE = "http://localhost:8001";

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

  // System
  backend_port: string;
  frontend_port: string;
  search_provider: string;
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
  backend_port: "8001",
  frontend_port: "3782",
  search_provider: "none",
};

export default function SettingsPage() {
  const [config, setConfig] = useState<Config>(DEFAULT_CONFIG);
  const [saved, setSaved] = useState(false);

  const set = <K extends keyof Config>(key: K, value: Config[K]) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    fetch(`${API_BASE}/api/v1/config`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    })
      .then(() => setSaved(true))
      .catch(() => {});
  };

  const handleReset = () => {
    setConfig(DEFAULT_CONFIG);
    setSaved(false);
  };

  const InputField = ({
    label,
    value,
    onChange,
    type = "text",
    placeholder,
    hint,
  }: {
    label: string;
    value: string | number;
    onChange: (v: string) => void;
    type?: string;
    placeholder?: string;
    hint?: string;
  }) => (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-zinc-400">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 placeholder-zinc-600 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
      />
      {hint && <p className="text-[11px] text-zinc-600">{hint}</p>}
    </div>
  );

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
    <div className="flex items-center justify-between">
      <div>
        <label className="text-xs text-zinc-400">{label}</label>
        {hint && <p className="text-[11px] text-zinc-600">{hint}</p>}
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative h-5 w-9 rounded-full transition-colors ${
          value ? "bg-indigo-600" : "bg-zinc-700"
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
    <div className="flex flex-col gap-1">
      <label className="text-xs text-zinc-400">{label}</label>
      {hint && <p className="text-[11px] text-zinc-600">{hint}</p>}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-100 focus:border-zinc-600 focus:outline-none focus:ring-1 focus:ring-zinc-600"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );

  const Section = ({
    title,
    icon: Icon,
    children,
  }: {
    title: string;
    icon: typeof Database;
    children: React.ReactNode;
  }) => (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-5 space-y-4">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-zinc-300">
        <Icon className="h-4 w-4" />
        {title}
      </h3>
      {children}
    </div>
  );

  return (
    <div className="flex flex-col gap-6 p-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="text-sm text-zinc-500">
            Configure LM Studio, model tiers, inference, and system parameters.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-1 rounded bg-zinc-800 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-zinc-200"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Reset
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-1 rounded bg-zinc-100 px-3 py-1.5 text-xs font-semibold text-zinc-900 transition-colors hover:bg-white"
          >
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
        </div>
      </div>

      {saved && (
        <div className="rounded-lg border border-emerald-900/50 bg-emerald-900/10 px-4 py-2 text-sm text-emerald-400">
          Configuration saved.
        </div>
      )}

      <Section title="LM Studio Connection" icon={Database}>
        <InputField
          label="Host"
          value={config.llm_host}
          onChange={(v) => set("llm_host", v)}
          placeholder="http://localhost"
        />
        <InputField
          label="Port"
          type="number"
          value={config.llm_port}
          onChange={(v) => set("llm_port", Number(v))}
        />
        <InputField
          label="API Key"
          value={config.llm_api_key}
          onChange={(v) => set("llm_api_key", v)}
          hint="Default: lm-studio"
        />
        <InputField
          label="Model"
          value={config.llm_model}
          onChange={(v) => set("llm_model", v)}
          placeholder="Qwen3-8B-Q4_K_M"
          hint="Primary LLM for inference"
        />
      </Section>

      <Section title="Embedding Model" icon={Database}>
        <InputField
          label="Host"
          value={config.embedding_host}
          onChange={(v) => set("embedding_host", v)}
          placeholder="http://localhost"
        />
        <InputField
          label="API Key"
          value={config.embedding_api_key}
          onChange={(v) => set("embedding_api_key", v)}
          hint="Default: lm-studio"
        />
        <InputField
          label="Model"
          value={config.embedding_model}
          onChange={(v) => set("embedding_model", v)}
          placeholder="Snowflake Arctic Embed M"
          hint="Embedding model for vector search"
        />
      </Section>

      <Section title="TurboQuant KV Cache" icon={Database}>
        <ToggleField
          label="Enabled"
          value={config.turboquant_enabled}
          onChange={(v) => set("turboquant_enabled", v)}
        />
        <SelectField
          label="Bit Width"
          value={config.turboquant_bits}
          options={[
            { value: "3", label: "3-bit" },
            { value: "4", label: "4-bit (recommended)" },
          ]}
          onChange={(v) => set("turboquant_bits", v)}
          hint="KV cache quantization bit width"
        />
        <InputField
          label="FP16 Residual Window"
          type="number"
          value={config.turboquant_resid}
          onChange={(v) => set("turboquant_resid", v)}
          hint="Tokens kept in full precision (128–256)"
        />
        <SelectField
          label="Integration Tier"
          value={config.turboquant_tier}
          options={[
            { value: "auto", label: "Auto-detect" },
            { value: "1", label: "Tier 1: LM Studio native" },
            { value: "2", label: "Tier 2: turboquant-server" },
            { value: "3", label: "Tier 3: app-layer Python" },
          ]}
          onChange={(v) => set("turboquant_tier", v)}
          hint="Auto-detects at startup"
        />
      </Section>

      <Section title="VRAM Pressure Management" icon={Database}>
        <InputField
          label="Safety Margin (%)"
          type="number"
          value={config.vram_safety_margin}
          onChange={(v) => set("vram_safety_margin", v)}
          hint="Reserved VRAM buffer (default: 15%)"
        />
        <InputField
          label="T2 Model TTL (seconds)"
          type="number"
          value={config.t2_ttl}
          onChange={(v) => set("t2_ttl", v)}
          hint="Idle timeout before T2 model unloads (default: 600)"
        />
        <InputField
          label="T3 Model TTL (seconds)"
          type="number"
          value={config.t3_ttl}
          onChange={(v) => set("t3_ttl", v)}
          hint="Idle timeout before T3 model unloads (default: 300)"
        />
      </Section>

      <Section title="System" icon={Database}>
        <div className="grid grid-cols-2 gap-4">
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
          label="Web Search"
          value={config.search_provider}
          options={[
            { value: "none", label: "None" },
            { value: "perplexity", label: "Perplexity" },
          ]}
          onChange={(v) => set("search_provider", v)}
          hint="Opt-in feature, requires API key"
        />
      </Section>
    </div>
  );
}
