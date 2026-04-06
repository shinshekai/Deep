// ─────────────────────────────────────────────
// UDIP API Type Mappings (from CLAUDE.md)
// ─────────────────────────────────────────────

// ── Document / PageIndex Types ──

export interface IndexNode {
  node_id: string;
  title: string;
  summary: string;
  start_index?: number;
  end_index?: number;
  children: IndexNode[];
}

// ── Model Tier Types ──

export type ModelTier = 1 | 2 | 3;

export interface ModelInfo {
  id: string;
  name: string;
  tier: ModelTier;
  status: "loaded" | "unloaded" | "loading";
  vram_used_mb: number;
  kv_cache_config: {
    cache_type_k: string;
    cache_type_v: string;
  };
  max_concurrent: number;
}

// ── VRAM / Cache Types ──

export type VramPressureLevel = "green" | "yellow" | "orange" | "red";

export interface CacheTelemetry {
  vram_total_mb: number;
  vram_used_mb: number;
  vram_used_pct: number;
  pressure_level: VramPressureLevel;
  active_models: ModelInfo[];
  turboquant_tier: string;
}

// ── Solve Query Types ──

export interface SolveQuery {
  query: string;
  kb_name: string;
  mode: "auto" | "detailed" | "quick";
  retrieval_pipeline: "tree" | "hybrid" | "naive" | "combined";
  session_id?: string;
}

export interface Citation {
  doc_id: string;
  page: number;
  section: string;
  node_id: string;
}

// ── WebSocket Solve Protocol Frames ──

export type AgentStepFrame = {
  type: "agent_step";
  agent: "investigate" | "note" | "plan" | "manager" | "solve" | "check" | "format";
  content: string;
  timestamp: number;
};

export type CitationFrame = {
  type: "citation";
  citation: Citation;
};

export type CompleteFrame = {
  type: "complete";
  answer: string;
  citations: Citation[];
  session_id: string;
  solve_dir: string;
};

export type ErrorFrame = {
  type: "error";
  error: string;
  message: string;
};

export type SolveFrame = AgentStepFrame | CitationFrame | CompleteFrame | ErrorFrame;

// ── Metrics Types (ws/metrics stream) ──

export type PipelineStage =
  | "PageIndex_Retrieval"
  | "DeepTutor_Reasoning"
  | "Final_Synthesis";

export interface InferenceTelemetryEvent {
  model_id: string;
  timestamp: number;
  pipeline_stage: PipelineStage;
  ttft_ms: number;
  tps_rate: number;
  total_tokens_processed: number;
  kv_compression_ratio: number;
}

export interface MetricsFrame {
  vram_used_mb: number;
  vram_total_mb: number;
  pressure_level: VramPressureLevel;
  active_models: string[];
  queue_depths: { retrieval: number; reasoning: number; generation: number };
  latency_ms: number;
  throughput_tps: number;
}

// ── Agent Log Events ──

export interface AgentLogEvent {
  agent_name: string;
  loop: "analysis" | "solve";
  timestamp: number;
  message: string;
  details?: Record<string, unknown>;
}

// ── Dashboard Routing Stats ──

export type RoutingStats = {
  cache_hit_rate: number;
  jit_load_frequency: number;
  eviction_count: number;
  model_hit_rate: number;
  queries_by_tier: { tier: number; count: number }[];
};

// ── Interactive UI Payloads ──

export interface InteractiveComponentPayload {
  type: "chart" | "table" | "flowchart" | "label-exercise" | string;
  data: Record<string, unknown>;
  componentId: string;
}