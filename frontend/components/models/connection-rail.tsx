"use client";

import { Cpu, Database, Server, Zap, Globe, Shield, Activity, Cloud, Key, Settings } from "lucide-react";
import type { ModelProvider } from "@/types/api";

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

interface ConnectionRailProps {
  localProviders: ModelProvider[];
  cloudProviders: ModelProvider[];
  onConfigure: (provider: ModelProvider) => void;
}

function ProviderCard({ provider, onConfigure }: { provider: ModelProvider; onConfigure: (p: ModelProvider) => void }) {
  const Icon = PROVIDER_ICONS[provider.id] || Cpu;
  const active = provider.status === "available";

  return (
    <div className="flex items-center justify-between group rounded-lg border border-zinc-900 hover:border-zinc-800 bg-zinc-950/20 px-3.5 py-2.5 transition">
      <div className="flex items-center gap-2.5 min-w-0">
        <span className="relative flex h-2 w-2 shrink-0">
          <span className={`relative inline-flex rounded-full h-2 w-2 ${active ? "bg-emerald-500" : "bg-zinc-700"}`} />
        </span>
        <Icon className="h-4 w-4 text-zinc-400 shrink-0" />
        <div className="min-w-0">
          <div className="text-xs font-semibold text-zinc-200 truncate">{provider.name}</div>
          <div className="text-[9px] font-mono text-zinc-500 truncate">
            {provider.base_url || (active ? "Connected" : "Inactive")}
          </div>
        </div>
      </div>
      <button
        type="button"
        onClick={() => onConfigure(provider)}
        className="p-1 rounded text-zinc-500 hover:text-white hover:bg-zinc-900 transition focus:outline-none"
        title={`Configure ${provider.name}`}
      >
        <Settings className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function ConnectionRail({ localProviders, cloudProviders, onConfigure }: ConnectionRailProps) {
  return (
    <section className="w-full lg:w-[25%] flex flex-col gap-6">
      <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-5">
        <div className="flex items-center justify-between border-b border-zinc-900 pb-3 mb-4">
          <span className="text-xs uppercase font-bold text-zinc-400 tracking-wider font-mono">Connection Rail</span>
          <span className="text-[10px] text-zinc-500">Local & Cloud Providers</span>
        </div>

        <div className="space-y-3 mb-6">
          <div className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider mb-2">Local Runtimes</div>
          {localProviders.map((provider) => (
            <ProviderCard key={provider.id} provider={provider} onConfigure={onConfigure} />
          ))}
        </div>

        <div className="space-y-3">
          <div className="text-[10px] uppercase font-bold text-zinc-500 tracking-wider mb-2">Cloud Provider APIs</div>
          {cloudProviders.map((provider) => (
            <ProviderCard key={provider.id} provider={provider} onConfigure={onConfigure} />
          ))}
        </div>
      </div>
    </section>
  );
}
