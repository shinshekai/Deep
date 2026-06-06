# Deep — Architecture

> High-level architecture of the Unified Document Intelligence Pipeline (UDIP).

## System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│ Frontend (Next.js 16.2, React 19.2)                              │
│  ├─ app/(platform)/chat      — Smart Solve chat interface       │
│  ├─ app/(platform)/solve     — Recursive solver UI              │
│  ├─ app/(platform)/knowledge — KB management                     │
│  ├─ app/(platform)/dashboard — Real-time telemetry               │
│  └─ components/dashboard/    — Telemetry visualizations         │
└──────────────────────────┬───────────────────────────────────────┘
                           │ WebSocket + REST
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ Backend (FastAPI 0.115, Python 3.10+)                            │
│  ├─ app/main.py + lifespan.py      — App entry + startup        │
│  ├─ app/middleware/                — Auth, CORS, rate-limit     │
│  ├─ app/routers/                   — knowledge, system, agent,  │
│  │                                   retrieval, query, memory   │
│  ├─ app/services/                  — 38+ domain services        │
│  │   ├─ base.py + service_registry — Service discovery          │
│  │   ├─ memory_service.py          — SQLite+FTS5 episodic mem   │
│  │   ├─ lm_studio_client.py        — OpenAI-compat LM Studio    │
│  │   ├─ recursive_solver.py        — 4-pattern recursive solve  │
│  │   ├─ solve_orchestrator.py      — Multi-step solve pipeline  │
│  │   ├─ document_processor.py      — PDF/Office/OCR extraction  │
│  │   ├─ fact_extractor.py          — LLM-based fact mining      │
│  │   ├─ telemetry.py               — OpenTelemetry spans        │
│  │   └─ ...                        — More (see file tree)       │
│  └─ app/websocket_handlers.py      — /api/v1/solve, /ws/metrics │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│ LM Studio (external)               │ Local data (data/)          │
│  └─ OpenAI-compatible LLM server   │  ├─ vector_kb/  (FAISS)     │
│     (e.g., Qwen3, Gemma 4)         │  ├─ user/       (sessions) │
│                                    │  └─ memory/     (SQLite)    │
└────────────────────────────────────┴─────────────────────────────┘
```

## Key Design Decisions

For "why" questions, see the ADRs in `docs/adr/`:

- ADR-0001: Use SQLite + FTS5 for local-first episodic memory
- ADR-0002: Use a custom DI Container for service lifecycle
- ADR-0003: Use OpenTelemetry for observability

## Architectural Pillars

1. **Local-first**: All data stays on the user's machine. No cloud
   dependencies. Multi-tenant posture is aspirational.

2. **Surgical modularity**: 38+ services discovered via `ServiceRegistry`
   (auto-discovery from `app/services/`). Each service is a single
   `async` class.

3. **Memory as a first-class system**: Episodic memory with FTS5 full-text
   search. Fact extraction via local LLM. Contradiction detection.

4. **Observability**: OpenTelemetry spans (now exporting via OTLP) +
   structured logging + Prometheus metrics. See `app/services/telemetry.py`.

5. **Recursive reasoning**: The 4-pattern recursive solver
   (`recursive_solver.py`) decomposes complex queries and synthesizes
   answers across multiple reasoning passes.

## Data Flow: Smart Solve

1. User submits query in chat UI
2. Frontend opens WebSocket to `/api/v1/solve`
3. Backend `ws_solve` issues per-connection `device_id` (UUID v4)
4. Backend routes to `recursive_solver` or `solve_orchestrator` based on
   query complexity
5. Solver retrieves context from KB (RAG), memory (episodic recall),
   and current state
6. LM Studio generates response in streaming chunks
7. Backend streams back to frontend via WebSocket frames
8. Frontend renders each frame incrementally
9. On completion, facts are extracted and stored in memory

## Security Model

- API token authentication (`X-DEEP-API-KEY`, `Authorization: Bearer`,
  or `?token=` query param)
- WebSocket ticket endpoint (`/api/auth/ws-ticket`) — token is server-
  side, never in the client bundle
- Rate limiting (SlowAPI middleware, default 100/min/IP)
- CORS restricted to explicit methods/headers
- Path traversal protection on document filenames
- Per-IP rate-limit on auth failures (10/min → 429)
- Memory namespace is per-user (`device_id`); no shared `default`
  namespace

## Performance Model

- Local-first: latency dominated by LLM inference
- All sync I/O (PDF, OCR, JSON) wrapped in `asyncio.to_thread`
- Memory: FTS5 for full-text, covering indexes on hot tables
- 4-pattern recursive solver: adaptive depth + early termination
- LM Studio: streaming + retry with exponential backoff
- No artificial delays in WebSocket solve frame

## Failure Modes

- LM Studio unavailable: fallback to stub response + flagged in metrics
- Memory service down: continue without memory; emit metric
- KB missing: return empty context; LLM degrades gracefully
- WebSocket disconnect: `in_flight` task is cancelled
- Auth failure: logged + audited + rate-limited per IP
