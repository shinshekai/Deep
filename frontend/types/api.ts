// ─────────────────────────────────────────────
// OpenAPI 3.1 Schema Mappings (from 02-system-architecture.md)
// ─────────────────────────────────────────────

export interface IndexNode {
  node_id: string;
  title: string;
  summary: string;
  start_index?: number;
  end_index?: number;
  children: IndexNode[];
}

export interface QueryRequest {
  session_id: string;
  query: string;
  force_tier?: number;
}

export interface QueryResponse {
  status: string;
  assigned_tier?: number;
}

export interface CacheTelemetry {
  vram_total_mb: number;
  vram_allocated_mb: number;
  condition_state: "green" | "yellow" | "red";
  active_models: string[];
  kv_compression_type: "turbo3" | "turbo4" | "q8_0" | "fp16";
}

export interface LMSStatsPassthrough {
  tokens_per_second: number;
  time_to_first_token: number;
  generation_time: number;
  stop_reason: string;
}

export interface ErrorResponse {
  error_code: string;
  message: string;
  fallback_triggered: boolean;
}

export interface HealthResponse {
  fastapi_status: string;
  llmster_daemon: string;
  workspace_sandbox: string;
}

// ─────────────────────────────────────────────
// WebSocket Telemetry Events
// (from 03-inference-strategy.md Section 5)
// ─────────────────────────────────────────────

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

export interface AgentLogEvent {
  agent_name: string;
  loop: "analysis" | "solve";
  timestamp: number;
  message: string;
  details?: Record<string, unknown>;
}

export interface InteractiveComponentPayload {
  type: "chart" | "table" | "flowchart" | "label-exercise" | string;
  data: Record<string, unknown>;
  componentId: string;
}

export type WSMessage =
  | { type: "telemetry"; data: InferenceTelemetryEvent }
  | { type: "cache"; data: CacheTelemetryEvent }
  | { type: "agent_log"; data: AgentLogEvent }
  | { type: "interactive"; data: InteractiveComponentPayload }
  | { type: "connection"; status: "open" | "close" | "error" };

// ─────────────────────────────────────────────
// Dashboard Routing Stats (REST polling)
// ─────────────────────────────────────────────

// Alias used in websocket event payloads
export type CacheTelemetryEvent = CacheTelemetry;

export type RoutingStats = {
  cache_hit_rate: number;
  jit_load_frequency: number;
  eviction_count: number;
  model_hit_rate: number;
  queries_by_tier: { tier: number; count: number }[];
};
