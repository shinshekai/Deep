# Deep — Architecture

> Comprehensive architecture of the Unified Document Intelligence Pipeline (UDIP).

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Frontend — Next.js 16.2 :3782                                           │
│  ├─ app/(platform)/chat          — Chat + Smart Solve streaming        │
│  ├─ app/(platform)/solve         — Recursive solver (decomposed)       │
│  ├─ app/(platform)/research      — Deep research pipeline              │
│  ├─ app/(platform)/guide         — Guided learning sessions            │
│  ├─ app/(platform)/questions     — Question generator                  │
│  ├─ app/(platform)/notebooks     — Notebooks + CoWriter + IdeaGen      │
│  ├─ app/(platform)/documents     — Document upload + management        │
│  ├─ app/(platform)/knowledge     — KB viewer + PageIndex trees         │
│  ├─ app/(platform)/dashboard     — Real-time telemetry                 │
│  ├─ app/(platform)/models        — Model management (decomposed)       │
│  ├─ app/(platform)/settings      — System configuration                │
│  │                                                                          │
│  ├─ components/                                                           │
│  │   ├─ ui/                    — 18 shadcn/ui Base-Nova components      │
│  │   │   ├─ badge, button, card, dialog, input, label                  │
│  │   │   ├─ popover, scroll-area, select, separator                    │
│  │   │   ├─ sheet, skeleton, sonner, switch, tabs                      │
│  │   │   └─ textarea, tooltip, accordion                               │
│  │   ├─ solve/                 — 12 components (9 extracted)            │
│  │   │   ├─ tree-item, sources-sidebar, solve-toolbar                  │
│  │   │   ├─ solve-composer, suggested-prompts, streaming-pipeline      │
│  │   │   ├─ error-banner, synthesis-result, page-index-sidebar         │
│  │   │   ├─ agent-step-display, citation-list, solve-input             │
│  │   │   └─ (decomposed from 987→347 line page)                        │
│  │   ├─ models/                — 4 components (extracted)               │
│  │   │   ├─ models-header, connection-rail, filter-toolbar             │
│  │   │   └─ tier-slot-card                                             │
│  │   │   └─ (decomposed from 932→230 line page)                        │
│  │   ├─ shared/                — Cross-page reusable                    │
│  │   │   └─ kb-selector         — KB selector (Chat + Sources)         │
│  │   ├─ deep/                  — DEEP-specific visuals                  │
│  │   │   ├─ agent-step-card, citation-inline                           │
│  │   │   └─ streaming-indicator, index.ts                              │
│  │   ├─ chat/                  — Chat components                        │
│  │   ├─ dashboard/             — Telemetry visualizations               │
│  │   ├─ documents/             — Upload + list                          │
│  │   └─ error-boundary.tsx     — Global error boundary                  │
│  │                                                                          │
│  ├─ providers/                   — WebSocket + Memory contexts         │
│  ├─ lib/                         — API clients, config, utilities      │
│  │   ├─ config.ts              — secureFetch + API_BASE_URL            │
│  │   ├─ knowledge.ts           — KB API client                         │
│  │   ├─ estimate-vram.ts       — VRAM estimation (extracted)           │
│  │   └─ utils.ts               — cn() (tailwind-merge + clsx)          │
│  └─ types/                       — TypeScript interfaces               │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │ WebSocket + REST (http://localhost:8001)
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Backend — FastAPI 0.136 :8001                                           │
│  ├─ main.py + lifespan.py              — App entry + startup/shutdown  │
│  ├─ state.py                           — Global singletons (11 services)│
│  ├─ config.py                          — pydantic-settings (40+ vars)  │
│  │                                                                          │
│  ├─ middleware/ (6 layers)              — Execution order (outer→inner):│
│  │   ├─ rate_limit.py                  — SlowAPI 100/min per IP        │
│  │   ├─ cors.py                        — Localhost origin pinning      │
│  │   ├─ metrics.py (MetricsMiddleware) — Prometheus counters/histogram │
│  │   ├─ correlation.py                 — X-Request-ID + ContextVar     │
│  │   ├─ headers.py                     — CSP, HSTS, X-Frame, COOP      │
│  │   └─ auth.py                        — Token validation (3 methods)  │
│  │                                                                          │
│  ├─ routers/ (7 routers)               — API layer:                    │
│  │   ├─ knowledge.py                   — Upload, KB CRUD, PageIndex    │
│  │   ├─ system.py                      — Health, config, models, VRAM  │
│  │   ├─ agent.py                       — Research, questions, learning │
│  │   ├─ retrieval.py                   — 5-mode retrieval pipeline     │
│  │   ├─ query.py                       — HTTP Q&A (non-streaming)      │
│  │   ├─ memory.py                      — Recall, episodes, facts       │
│  │   └─ validation_routes.py           — Self-validation framework     │
│  │                                                                          │
│  ├─ services/ (38+ services)           — Business logic:               │
│  │   │                                                                       │
│  │   ├─ [Inference]                                                                │
│  │   │  lm_studio_client.py          — LM Studio API client (httpx)  │
│  │   │  model_manager.py             — 3-tier lifecycle (T1/T2/T3)    │
│  │   │  model_discovery.py           — Auto-discover local + cloud    │
│  │   │  vram_monitor.py              — pynvml GPU pressure (4 levels) │
│  │   │  embedding_service.py         — Text embedding via LM Studio   │
│  │   │  response_cache.py            — SHA-256 content-addressed cache │
│  │   │  prompt_registry.py           — YAML prompt management          │
│  │   │                                                                       │
│  │   ├─ [Retrieval & RAG]                                                      │
│  │   │  retrieval_service.py         — Pipeline dispatch (5 modes)     │
│  │   │  query_router.py              — Auto-select retrieval mode      │
│  │   │  complexity_scorer.py         — 4-signal complexity scoring     │
│  │   │  tree_search.py               — PageIndex tree reasoning        │
│  │   │  vector_kb.py                 — Local numpy vector store        │
│  │   │  hybrid_rag.py                — RRF merge (vector + keyword)    │
│  │   │  pageindex_generator.py       — 3-pass document indexing        │
│  │   │  knowledge_graph.py           — Entity-relation KG for RAG     │
│  │   │  rag_eval.py                  — Faithfulness + relevancy eval   │
│  │   │                                                                       │
│  │   ├─ [Agents]                                                                │
│  │   │  solve_orchestrator.py        — Dual-loop smart solver          │
│  │   │  recursive_solver.py          — 4-pattern multi-agent solver    │
│  │   │  deep_research.py             — 3-phase research pipeline       │
│  │   │  guided_learning.py           — 4-agent adaptive tutoring       │
│  │   │  question_generator.py        — Question gen + validation       │
│  │   │  content_creation.py          — Notebooks, CoWriter, IdeaGen    │
│  │   │  ara_compiler.py              — 4-layer knowledge compilation   │
│  │   │                                                                       │
│  │   ├─ [Memory]                                                                │
│  │   │  memory_service.py            — SQLite+FTS5 (14 tables)         │
│  │   │  memory_context.py            — 2000-token context builder      │
│  │   │  memory_maintenance.py        — Decay, compaction, pruning      │
│  │   │  fact_extractor.py            — LLM fact extraction + profiles  │
│  │   │                                                                       │
│  │   ├─ [Document Processing]                                                   │
│  │   │  document_processor.py        — PDF/DOCX/TXT/MD extraction     │
│  │   │  text_extractor.py            — Page-range text mapping         │
│  │   │  text_chunker.py              — Recursive character splitting   │
│  │   │  ocr_engine.py                — pytesseract / easyocr           │
│  │   │                                                                       │
│  │   └─ [Infrastructure]                                                       │
│  │      base.py                      — ServiceRegistry + DI            │
│  │      security.py                  — SSRF, path sanitize, auth       │
│  │      secrets.py                   — OS keyring integration          │
│  │      audit.py                     — Security audit trail            │
│  │      metrics.py                   — Prometheus + MetricsMiddleware  │
│  │      telemetry.py                 — OpenTelemetry (optional)        │
│  │      alerting.py                  — VRAM/error rate alerts          │
│  │      backup.py                    — KB backup + restore             │
│  │      benchmark_runner.py          — Performance benchmarks          │
│  │      logging_config.py            — Structured JSON logging         │
│  │      session_cleanup.py           — Stale session pruning           │
│  │      task_registry.py             — Async task lifecycle tracking   │
│  │      task_wal.py                  — Write-ahead log for crash recov │
│  │                                                                          │
│  ├─ websocket_handlers.py              — /api/v1/solve + /ws/metrics   │
│  │                                                                          │
│  ├─ validation/ (7 modules)            — Self-validation framework:    │
│  │   ├─ baselines.py                  — Thresholds + data classes      │
│  │   ├─ config_validator.py           — Static config analysis         │
│  │   ├─ coverage_tracker.py           — pytest coverage measurement    │
│  │   ├─ health_checker.py             — LM Studio + Phase 10 checks    │
│  │   ├─ remediation_tracker.py        — 18 sprint items                │
│  │   ├─ runner.py                     — CLI orchestrator               │
│  │   └─ validation_routes.py          — REST API for validation        │
│  │                                                                          │
│  └─ prompts/                         — YAML prompt templates           │
│      ├─ fact_extraction.yaml                                                         │
│      ├─ rag_judge.yaml                                                                │
│      └─ solve_agents.yaml                                                             │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
┌──────────────────┐ ┌────────────┐ ┌──────────────────┐
│ LM Studio :1234  │ │ SQLite     │ │ Filesystem       │
│ OpenAI-compat    │ │ + FTS5     │ │                  │
│ API              │ │            │ │ data/            │
│                  │ │ data/      │ │  ├─ memory/      │
│ Models:          │ │  memory/   │ │  ├─ vector_kb/   │
│  T1: e2b/e4b     │ │  deep_     │ │  ├─ knowledge_   │
│  T2: 9b/glm      │ │  memory.db │ │  │   bases/      │
│  T3: 26b/12b     │ │            │ │  └─ backups/     │
└──────────────────┘ └────────────┘ └──────────────────┘
```

## Architectural Pillars

### 1. Local-First
All data stays on the user's machine. No cloud dependencies. Inference via LM Studio, Ollama, or llama.cpp. Device-scoped privacy with UUID v4 identifiers. OS keyring integration for secrets.

### 2. Surgical Modularity
38+ services discovered via `ServiceRegistry` (`app/services/base.py`). Each service is a single async class with clear boundaries. DI container supports singleton/transient lifetimes with test overrides.

### 3. Memory as First-Class System
14-table SQLite database with FTS5 full-text search. Episodic recall with recency weighting (0.6 FTS + 0.4 recency). Fact extraction via local LLM. Contradiction detection (Jaccard + negation). Progressive crystallization. Dead-end tracking. L3 cross-surface synthesis.

### 4. Observability
OpenTelemetry tracing (optional OTLP export) + Prometheus metrics + structured JSON logging + WebSocket telemetry broadcast. VRAM pressure monitoring (4 levels: GREEN/YELLOW/ORANGE/RED).

### 5. Recursive Reasoning
4-pattern recursive solver (Sequential, Mixture, Deliberation, Distillation) + dual-loop smart solver (Analysis: Investigate→Note, Solve: Plan→Solve→Check→Format). Complexity-scored routing selects the right agent and model tier.

### 6. Production Hardening
Docker containers with read-only filesystems, capability dropping, resource limits. Blue-green zero-downtime deployment. CI/CD with 11 jobs including Trivy scanning, SBOM generation, and Locust load testing.

### 7. Component-Driven UI
shadcn/ui Base-Nova design system with `@base-ui/react` primitives. Dark-only oklch theme. Tailwind CSS v4. Pages decomposed into focused components (solve: 12 components, models: 4 components). Shared components (KbSelector) reused across pages. Sonner unified toasts across all 8 pages.

## Middleware Stack

Execution order (outermost first, each wraps the next):

| # | Middleware | File | Purpose |
|---|-----------|------|---------|
| 1 | Rate Limiting | `middleware/rate_limit.py` | SlowAPI, 100/min per IP |
| 2 | CORS | `middleware/cors.py` | Localhost origin pinning |
| 3 | Metrics | `services/metrics.py` | Prometheus counters/histograms |
| 4 | Correlation | `middleware/correlation.py` | X-Request-ID + ContextVar |
| 5 | Security Headers | `middleware/headers.py` | CSP, HSTS, X-Frame, COOP, Referrer-Policy |
| 6 | Auth | `middleware/auth.py` | Token validation (3 methods), error sanitization |
| 7 | OpenTelemetry | FastAPIInstrumentor | Distributed tracing (optional) |

## Memory System

### Tables (14)

| Table | Purpose |
|-------|---------|
| `episodes` | Chat/session history with query, answer, agents, model, rating, provenance |
| `episode_chunks` | FTS-indexed text chunks of episodes |
| `episodes_fts` | FTS5 virtual table (porter unicode61 tokenizer) |
| `facts` | Extracted knowledge facts with confidence, access tracking, provenance |
| `fact_chunks` | FTS-indexed text chunks of facts |
| `facts_fts` | FTS5 virtual table |
| `user_profiles` | Per-device JSON profiles with staleness tracking |
| `agent_outcomes` | Agent performance records (type, strategy, quality, tier) |
| `agent_strategies` | Best-strategy aggregation per agent type + pattern |
| `project_profiles` | Global KB metadata (doc count, pages, last queried) |
| `staged_observations` | Progressive crystallization buffer |
| `dead_ends` | Failed research paths with hypotheses and lessons |
| `user_l3` | L3 cross-surface synthesis (4 slots) |
| `provenance_log` | Audit trail for provenance upgrades |

### Recall Scoring

- **Episodes**: `0.6 × FTS5_rank + 0.4 × recency_decay` (exponential, 30-day half-life)
- **Facts**: `0.4 × FTS5_rank + 0.3 × recency_decay + 0.3 × confidence`
- **Budget**: 2000 tokens max context injection

### Maintenance

- **Decay**: Hourly, 30-day half-life reduces confidence of old facts
- **Compaction**: Merges similar episodes older than 90 days
- **FTS5 Reindex**: Periodic reindexing for optimal search
- **Progressive Crystallization**: Observations staged before permanent storage

## Agent System

### Complexity Routing

4-signal weighted scoring routes queries to the appropriate agent:

| Signal | Weight | Source |
|--------|--------|--------|
| Query complexity | 0.35 | Token count, question words, technical terms |
| Document size | 0.25 | Average chunk length, document count |
| Chunk count | 0.15 | Available context chunks |
| VRAM available | 0.25 | GPU memory headroom |

### Smart Solver (Dual-Loop)

```
Analysis Loop                    Solve Loop
┌──────────────────┐            ┌──────────────────┐
│ Investigate      │            │ Plan             │
│   ↓              │  Sufficient│   ↓              │
│ Note             │──context──→│ Solve            │
│   ↓              │            │   ↓              │
│ Sufficient? ──No─┘            │ Check            │
│                 Yes           │   ↓              │
└──────────────────┘            │ Format           │
                                └──────────────────┘
```

### Recursive Solver (4 Patterns)

| Pattern | Description | Best For |
|---------|-------------|----------|
| Sequential | Agents process in chain | Step-by-step problems |
| Multiple | Multiple agents solve independently, outputs merged | Diverse perspectives |
| Deliberation | Agents debate and refine through rounds | Nuanced topics |
| Distillation | Multiple outputs compressed into single best answer | High-quality final output |

### Retrieval Modes

| Mode | Pipeline | When Used |
|------|----------|-----------|
| Tree | LLM reasoning over PageIndex | Documents with hierarchical structure |
| Hybrid | Vector + keyword RRF merge | General queries |
| Naive | Vector similarity only | Simple lookups |
| Combined | Tree + Hybrid | Complex multi-source queries |
| ARA | Agent-Native Research Artifact | Research-grade queries |

## Data Flow: Query Processing

```
1. User submits query (chat or HTTP)
2. Frontend sends to backend (WebSocket /api/v1/solve or POST /api/v1/query)
3. Memory recall: episodic + factual + L3 context
4. Complexity scoring (4 signals)
5. Agent routing (smart solver / recursive solver / research / learning)
6. Retrieval pipeline execution (tree/hybrid/naive/combined/ARA)
7. LLM generation via LM Studio (streaming)
8. Response caching (SHA-256 content-addressed)
9. Fact extraction and storage
10. Episode storage with FTS indexing
11. Response streamed to frontend
```

## Data Flow: Document Processing

```
1. User uploads document (PDF/DOCX/TXT/MD)
2. File validation (type, size, MIME, disk space)
3. Text extraction (PyMuPDF + OCR fallback)
4. Text chunking (recursive character splitting)
5. Parallel processing:
   ├─ PageIndex tree generation (3-pass)
   ├─ Vector embedding (LM Studio /v1/embeddings)
   └─ ARA compilation (Logic/Solution/Trace/Evidence)
6. Knowledge graph entity extraction
7. Document metadata stored
8. Task status updated for polling
```

## Security Model

- **Authentication**: 3 methods (X-DEEP-API-KEY, Bearer token, query param) with constant-time comparison
- **WebSocket**: First-message auth (token sent as JSON, not URL query param)
- **Rate Limiting**: 100/min per IP, per-IP auth failure tracking (10/60s)
- **SSRF Protection**: DNS validation, cloud metadata blocking, private IP blocking
- **Path Sanitization**: `safe_name()`, `safe_doc_id()`, `resolve_within()`
- **Security Headers**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options, COOP, Referrer-Policy
- **Memory Isolation**: Per-device UUID v4, no cross-device data leakage
- **Docker**: Read-only filesystems, capability dropping, non-root users

## Performance Model

- **Latency**: Dominated by LLM inference (local-first)
- **Memory**: FTS5 with covering indexes on hot tables
- **Concurrency**: 3-tier semaphore (T1: 4, T2: 2, T3: 1)
- **Caching**: LRU model cache, embedding cache, query response cache
- **TurboQuant**: 3-4 bit KV cache compression (40-50% VRAM reduction)
- **VRAM Management**: Real-time pynvml monitoring, 4-level pressure response

## Failure Modes

| Failure | Mitigation |
|---------|-----------|
| LM Studio unavailable | Fallback to stub response, flagged in metrics |
| Memory service down | Continue without memory, emit metric |
| KB missing | Return empty context, LLM degrades gracefully |
| WebSocket disconnect | `in_flight` task cancelled |
| Auth failure | Logged, audited, rate-limited per IP |
| VRAM exhaustion | Evict T3→T2→T1 models by pressure level |
| Disk full | 507 check before upload, graceful rejection |
| Model not found | Bail-early on unload, skip phantom verification |

## Infrastructure

### Docker Compose Variants

| File | Use Case | Key Features |
|------|----------|--------------|
| `docker-compose.yml` | Development | Simple two-service setup |
| `docker-compose.prod.yml` | Production | Read-only, caps, resource limits, health checks |
| `docker-compose.blue-green.yml` | Zero-downtime | 5 services (nginx + blue/green pairs) |

### CI/CD Pipeline (11 Jobs)

| Job | Trigger | Description |
|-----|---------|-------------|
| Static Validation | Every commit | YAML, JSON, Dockerfile lint |
| Backend Tests | Every commit | pytest + mypy + coverage (80% min) |
| Frontend Checks | Every commit | TypeScript + lint + build |
| Security Scan | Every commit | pip-audit + npm audit |
| Full Validation | Nightly | Full validation suite |
| Docker Build | main/develop | Multi-platform image + Trivy scan |
| Load Test | Nightly | Locust (50 users, 10/sec) |
| Remediation Gate | PRs | Sprint progress tracking |
| SBOM | main | CycloneDX for Python + Node.js |
| Commit Lint | PRs | Conventional Commits format |
| Cloud Deploy | Tags (v1.*) | Production deployment |

### Blue-Green Deployment

```
                    ┌─────────┐
                    │  nginx  │ :80/:443
                    └────┬────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        ┌──────────┐          ┌──────────┐
        │  blue    │          │  green   │
        │ backend  │          │ backend  │
        │ frontend │          │ frontend │
        └──────────┘          └──────────┘
```

Deploy → Build inactive color → Health check → Switch nginx → Drain old → Repeat.

## Repository Structure

```
Deep/
├── backend/                    # FastAPI Python 3.14 backend
│   ├── app/
│   │   ├── main.py             # Entry point
│   │   ├── config.py           # Settings (pydantic-settings)
│   │   ├── state.py            # Global singletons
│   │   ├── lifespan.py         # Startup/shutdown
│   │   ├── dependencies.py     # DI container
│   │   ├── websocket_handlers.py
│   │   ├── middleware/          # 6 middleware layers
│   │   ├── routers/            # 7 API routers
│   │   ├── services/           # 38+ business logic services
│   │   ├── validation/         # Self-validation framework
│   │   └── prompts/            # YAML prompt templates
│   ├── tests/                  # 62 test files, 556 tests
│   ├── turboquant_plus/        # KV cache quantization (embedded)
│   ├── requirements.txt        # Pinned production deps
│   └── requirements-dev.txt    # Pinned dev/test deps
├── frontend/                   # Next.js 16.2 TypeScript frontend
│   ├── app/(platform)/         # 12 pages
│   ├── components/
│   │   ├── ui/                 # 18 shadcn/ui Base-Nova components
│   │   ├── solve/              # 12 decomposed solve components
│   │   ├── models/             # 4 decomposed model components
│   │   ├── shared/             # Shared cross-page components
│   │   ├── deep/               # DEEP-specific visuals
│   │   ├── chat/               # Chat components
│   │   ├── dashboard/          # Telemetry visualizations
│   │   ├── documents/          # Upload + list
│   │   └── error-boundary.tsx  # Global error boundary
│   ├── providers/              # WebSocket + Memory contexts
│   ├── lib/                    # API clients + utilities
│   └── __tests__/              # 8 test files, 43 tests
├── scripts/                    # Deployment + tooling
├── .github/workflows/          # CI/CD (11 jobs)
├── docker-compose*.yml         # Dev, prod, blue-green
├── ARCHITECTURE.md             # This file
├── ACKNOWLEDGEMENTS.md         # Research attributions
├── SECURITY.md                 # Security policy
└── CONTRIBUTING.md             # Contribution guide
```
