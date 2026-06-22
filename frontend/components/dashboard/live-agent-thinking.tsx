"use client";

import { useState, useEffect } from "react";
import { useWebSocket } from "@/providers/websocket-provider";
import { Brain, Cpu, Zap, Clock, ArrowRight, CheckCircle2 } from "lucide-react";

interface AgentStep {
  agent: string;
  delta: string;
  timestamp: number;
}

export function LiveAgentThinking() {
  const { solveStatus, subscribe } = useWebSocket();
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number>(0);

  useEffect(() => {
    const unsub = subscribe("agent_step", (data: Record<string, unknown>) => {
      const step: AgentStep = {
        agent: String(data?.agent || "unknown"),
        delta: String(data?.delta || "").slice(0, 200),
        timestamp: Number(data?.timestamp || Date.now()),
      };
      setSteps((prev) => [...prev.slice(-20), step]);
      setCurrentAgent(step.agent);
      setLastUpdate(step.timestamp);
    });
    return unsub;
  }, [subscribe]);

  const isActive = solveStatus === "open" && Date.now() - lastUpdate < 30000;

  return (
    <div className="rounded-xl border border-zinc-900 bg-zinc-950/40 p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-zinc-900 pb-2">
        <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-zinc-400 tracking-wider font-mono">
          <Brain className={`h-3.5 w-3.5 ${isActive ? "text-indigo-400 animate-pulse" : "text-zinc-600"}`} />
          <span>Live Agent Thinking</span>
        </div>
        <span className={`text-[9px] font-mono ${isActive ? "text-indigo-400" : "text-zinc-600"}`}>
          {isActive ? "ACTIVE" : "IDLE"}
        </span>
      </div>

      {currentAgent && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-indigo-900/30 bg-indigo-950/10">
          <Cpu className="h-4 w-4 text-indigo-400" />
          <div>
            <div className="text-xs font-bold text-indigo-300 font-mono uppercase">{currentAgent}</div>
            <div className="text-[10px] text-indigo-400/60 font-mono mt-0.5">
              {steps.length} steps recorded
            </div>
          </div>
          <Clock className="h-3 w-3 text-zinc-600 ml-auto" />
        </div>
      )}

      <div className="space-y-2 max-h-60 overflow-y-auto deep-scrollbar pr-1">
        {steps.length === 0 && (
          <div className="text-center py-6 text-[10px] text-zinc-600 font-mono">
            <Zap className="h-5 w-5 mx-auto mb-2 text-zinc-700" />
            Awaiting agent activity...
          </div>
        )}
        {steps.slice(-8).reverse().map((step, i) => (
          <div
            key={`${step.timestamp}-${i}`}
            className="flex items-start gap-2 p-2 rounded border border-zinc-900/50 bg-zinc-950/20 text-[10px]"
          >
            <ArrowRight className="h-3 w-3 text-zinc-600 mt-0.5 shrink-0" />
            <div className="min-w-0">
              <span className="font-bold text-zinc-400 font-mono uppercase">{step.agent}</span>
              <span className="text-zinc-500 ml-1 break-all line-clamp-2">{step.delta}</span>
            </div>
            {i === 0 && <CheckCircle2 className="h-3 w-3 text-emerald-500 shrink-0 ml-auto" />}
          </div>
        ))}
      </div>
    </div>
  );
}
