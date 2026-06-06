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
  status: "loaded" | "unloaded" | "loading" | "available";
  vram_used_mb: number;
  turboquant_config?: {
    cache_type_k?: string;
    cache_type_v?: string;
  };
  max_concurrent: number;
}

export type ModelProviderSource = "local" | "cloud";

export interface DiscoveredModel {
  id: string;
  name: string;
  provider_id: string;
  source: ModelProviderSource;
  openai_compatible: boolean;
  metadata?: {
    object?: string;
    family?: string;
    parameter_size?: string;
    quantization_level?: string;
    context_length?: number | string;
    capabilities?: string[];
    context_length_cat?: string;
    parameter_size_cat?: string;
  };
}

export interface ModelProvider {
  id: string;
  name: string;
  source: ModelProviderSource;
  status: "available" | "unavailable" | "not_configured";
  configured: boolean;
  openai_compatible: boolean;
  base_url?: string;
  error?: string;
  models: DiscoveredModel[];
  description?: string;
  cost_hint?: string;
  latency_hint?: string;
  setup_docs_url?: string;
}

export interface ActiveModelSelection {
  provider_type: ModelProviderSource;
  provider_id: string;
  model_id: string;
  selected_at?: number;
}

export interface ModelDiscoveryResponse {
  local: ModelProvider[];
  cloud: ModelProvider[];
  active_selection: ActiveModelSelection | null;
  active_selections?: Record<string, ActiveModelSelection | null>;
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
  metadata?: {
    elapsed_seconds: number;
    complexity_score: number;
    model_used: string;
  };
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
