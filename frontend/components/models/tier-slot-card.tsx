"use client";

import { Check, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { DiscoveredModel } from "@/types/api";
import { estimateVramNeeds } from "@/lib/estimate-vram";

type ActiveSelection = { model_id: string; provider_id: string } | null;

interface TierSlotCardProps {
  tier: "T1" | "T2" | "T3";
  slotLabel: string;
  title: string;
  description: string;
  activeSelection: ActiveSelection;
  models: DiscoveredModel[];
  selecting: string | null;
  onSelect: (model: DiscoveredModel) => void;
  showVramEstimate?: boolean;
  fallbackName?: string;
}

export function TierSlotCard({
  tier,
  slotLabel,
  title,
  description,
  activeSelection,
  models,
  selecting,
  onSelect,
  showVramEstimate,
  fallbackName,
}: TierSlotCardProps) {
  return (
    <div className="flex flex-col rounded-xl border border-zinc-900 bg-zinc-950/60 overflow-hidden">
      <div className="bg-indigo-950/10 border-b border-zinc-900 p-4">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold font-mono text-indigo-400 uppercase tracking-widest bg-indigo-950/40 border border-indigo-900/30 px-1.5 py-0.5 rounded">{tier}</span>
          <span className="text-[10px] font-semibold text-zinc-500">{slotLabel}</span>
        </div>
        <h3 className="text-sm font-bold text-zinc-200 mt-2">{title}</h3>
        <p className="text-[11px] text-zinc-400 mt-1 leading-normal">{description}</p>
      </div>

      <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 grow">
        <span className="text-[9px] uppercase font-bold text-zinc-500 font-mono tracking-wider">Active Route:</span>
        {activeSelection ? (
          <div className="mt-2.5 flex items-start gap-2 bg-emerald-950/5 border border-emerald-900/20 rounded p-2 text-xs">
            <Check className="h-4.5 w-4.5 text-emerald-400 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <div className="font-semibold text-zinc-200 break-all">{activeSelection.model_id}</div>
              <div className="text-[9px] font-mono text-zinc-400 mt-0.5 uppercase tracking-wider">{activeSelection.provider_id}</div>
            </div>
          </div>
        ) : (
          <div className="mt-2.5 flex items-start gap-2 bg-yellow-950/5 border border-yellow-900/20 rounded p-2 text-xs">
            <AlertTriangle className="h-4.5 w-4.5 text-yellow-500 shrink-0 mt-0.5" />
            <div className="min-w-0">
              <div className="font-semibold text-yellow-400">Safe Fallback Cascade</div>
              {fallbackName && <div className="text-[9px] text-zinc-400 mt-0.5">{fallbackName}</div>}
            </div>
          </div>
        )}
      </div>

      <div className="p-4 flex flex-col gap-2 max-h-[300px] overflow-y-auto">
        <span className="text-[9px] uppercase font-bold text-zinc-500 font-mono tracking-wider">Discovered Targets:</span>
        {models.length === 0 ? (
          <div className="text-[11px] text-zinc-500 text-center py-6">No matching models configured.</div>
        ) : (
          models.map((model) => {
            const isActive = activeSelection?.model_id === model.id && activeSelection?.provider_id === model.provider_id;
            const est = showVramEstimate ? estimateVramNeeds(model) : null;
            return (
              <button
                key={model.id}
                onClick={() => onSelect(model)}
                disabled={isActive || Boolean(selecting)}
                className={`flex flex-col text-left p-2.5 rounded-lg border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/40 ${
                  isActive
                    ? "bg-emerald-950/10 border-emerald-900/30 text-emerald-300"
                    : "bg-zinc-950 border-zinc-900 hover:border-zinc-800 text-zinc-300"
                }`}
              >
                <div className="font-semibold text-xs break-all">{model.name}</div>
                <div className="flex justify-between items-center w-full mt-1.5">
                  <span className="text-[9px] font-mono text-zinc-500 uppercase">{model.provider_id}</span>
                  {est ? (
                    <Badge className="bg-zinc-900 text-zinc-400 border-zinc-850 px-1 py-0 text-[8px]">{est.totalGb} GB est</Badge>
                  ) : isActive ? (
                    <span className="text-[9px] text-emerald-400 font-semibold font-mono uppercase tracking-wider">ACTIVE</span>
                  ) : null}
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
