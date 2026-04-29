@AGENTS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UDIP (Unified Document Intelligence Pipeline) is a local-first, web-based AI application that merges three systems into a unified document intelligence pipeline:

- **DeepTutor** — Multi-agent AI tutoring, Q&A, deep research, question generation, and idea generation
- **PageIndex** — Vectorless, reasoning-based hierarchical document indexing with page-level traceability
- **TurboQuant** — KV cache quantization (3–4 bit) via PolarQuant + QJL for memory-efficient inference on consumer GPUs

The application ingests documents (PDF/TXT/MD), builds hierarchical semantic indexes, and enables multi-modal AI interactions entirely on local hardware with no cloud dependencies.

## Technology Stack

| Layer | Technology | Port |
|-------|-----------|------|
| Frontend | React / Next.js 16+ | 3782 |
| Backend | Python 3.10+ / FastAPI | 8001 |
| Inference | LM Studio (OpenAI-compatible API) | 1234 |
| Storage | Local filesystem (`data/` directory) | — |

## Architecture

### Three-Tier Model System

All LLM inference flows through a three-tier model architecture with LM Studio:

| Tier | Role | Models | VRAM | KV Cache | Max Concurrent |
|------|------|--------|------|----------|----------------|
| T1 (Always Resident) | Embedding, retrieval scoring, query classification | Qwen3-0.6B, Qwen3-1.7B (Q4_K_M) | 0.5–1.2 GB | K:q4_0/V:q4_0 | 4 |
| T2 (Semi-Resident) | Reasoning, chunk re-ranking, query decomposition | Qwen3-4B, Qwen3-8B (Q4–Q5) | 2.5–5.5 GB | K:q8_0/V:q4_0 | 2 |
| T3 (On-Demand) | Final synthesis, multi-hop reasoning | Qwen3-14B, Qwen3-30B-A3B MoE (Q4_K_M) | 8.5–18 GB | K:q8_0/V:q8_0 | 1 |

**Embedding model** (separate from LLM tiers): Snowflake Arctic Embed M (GGUF) default, nomic-embed-text-v1.5 or BGE-M3 configurable via `EMBEDDING_MODEL`.

### Core Backend Components

```
FastAPI Backend (:8001)
├── API Layer
│   ├── REST API (/api/v1/*)
│   ├── WebSocket — Smart Solver (ws://localhost:8001/api/v1/solve)
│   └── WebSocket — Metrics (ws://localhost:8001/ws/metrics)
├── Orchestration Layer
│   ├── PriorityQueue (RETRIEVAL:Sem=4, REASONING:Sem=2, GENERATION:Sem=1)
│   ├── ModelManager (tier selection, TTL-based lifecycle, fallback cascade)
│   ├── VRAM Monitor (pynvml, 2s poll, GREEN/YELLOW/ORANGE/RED pressure levels)
│   └── Complexity Scorer (4-signal weighted: query 0.35, doc_size 0.25, chunks 0.15, VRAM 0.25)
├── DeepTutor Agent Suite
│   ├── Smart Solver (dual-loop: Analysis [Investigate+Note] → Solve [Plan+Manager+Solve+Check+Format])
│   ├── Deep Research (3-phase: Plan → Research → Report, Dynamic Topic Queue, max 5 concurrent)
│   ├── Guided Learning (Locate → Interactive → Chat → Summary)
│   ├── Question Generator (custom + exam mimicry)
│   └── IdeaGen (interactive co-writer + automated)
├── Retrieval Layer
│   ├── PageIndex Tree Search (reasoning-based, page-level citations)
│   ├── Hybrid RAG (vector + keyword)
│   ├── Naive RAG (pure vector similarity)
│   └── Query Router (tree/hybrid/naive/combined)
├── Document Processing
│   ├── Document Parser (PyMuPDF / Docling)
│   ├── PageIndex Tree Generator (hierarchical JSON)
│   ├── Vector KB Builder (embedding pipeline)
│   └── Numbered Item Extractor
├── KV Cache Layer (TurboQuant)
│   ├── TurboQuant Config (Tier 1: LM Studio native / Tier 2: turboquant-server / Tier 3: app-layer)
│   └── KV Cache Policy (asymmetric quantization per tier, FP16 residual window 128–256 tokens)
└── Observability
    ├── OpenTelemetry (7 instrumentation points, Jaeger export)
    └── MetricsCollector (VRAM, latency, queue depth, throughput)
```

### Data Storage Layout

```
data/
├── knowledge_bases/{kb_name}/
│   ├── pageindex/{doc_id}.json    # Hierarchical tree indexes
│   ├── vectors/                    # Embedding-based knowledge base
│   └── items/                      # Extracted numbered items
├── user/
│   ├── solve/solve_YYYYMMDD_HHMMSS/   # Smart Solver session artifacts
│   ├── guide/session_{id}.json         # Guided Learning summaries
│   ├── co-writer/audio/                # TTS narration files
│   └── notebooks/                      # Unified learning records
└── cache/                              # KV cache metadata
```

## Key API Endpoints

### REST Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/knowledge/upload` | Upload document (PDF/TXT/MD), triggers parallel PageIndex tree + vector KB generation |
| GET | `/api/v1/knowledge/tasks/{task_id}` | Poll document processing progress |
| GET | `/api/v1/knowledge/bases` | List all knowledge bases |
| GET | `/api/v1/knowledge/bases/{kb_name}` | Get KB details |
| DELETE | `/api/v1/knowledge/bases/{kb_name}` | Delete a KB |
| GET | `/api/v1/knowledge/bases/{kb_name}/pageindex/{doc_id}` | Retrieve PageIndex tree JSON |
| POST | `/api/v1/retrieve` | Execute retrieval (tree/hybrid/naive/combined pipeline) |
| POST | `/api/v1/query` | HTTP fallback for synchronous Q&A (non-streaming) |
| POST | `/api/v1/research` | Start Deep Research session (3-phase pipeline) |
| POST | `/api/v1/questions/generate` | Generate practice questions from KB |
| POST | `/api/v1/learning/start` | Start guided learning session |
| GET | `/api/v1/models` | List all models with tier assignments and status |
| POST | `/api/v1/models/{model_id}/load` | Load model into VRAM |
| POST | `/api/v1/models/{model_id}/unload` | Unload model from VRAM |
| GET | `/api/v1/cache/status` | KV cache status across all models |
| PUT | `/api/v1/cache/config` | Update TurboQuant KV cache config |
| POST | `/api/v1/cache/evict` | Manually trigger KV cache eviction |
| GET | `/api/v1/vram/status` | GPU VRAM status and pressure level |
| GET | `/api/v1/metrics/history` | Historical metrics timeseries |
| POST | `/api/v1/metrics/benchmarks/run` | Trigger benchmark suite (categories A/B/C/D) |
| GET | `/api/v1/health` | System health check (LM Studio, GPU, TurboQuant tier detection) |
| GET/PUT | `/api/v1/config` | System configuration |

### WebSocket Endpoints

- `ws://localhost:8001/api/v1/solve` — Smart Solver streaming (client sends query JSON, server streams agent steps as JSON frames)
- `ws://localhost:8001/ws/metrics` — Real-time metrics broadcast (2s interval, MetricsFrame JSON)

### WebSocket Solve Protocol

**Client → Server:**
```json
{"query": "...", "kb_name": "...", "mode": "auto|detailed|quick", "retrieval_pipeline": "tree|hybrid|naive|combined", "session_id": "..."}
```

**Server → Client frames:**
```json
{"type": "agent_step", "agent": "investigate|note|plan|manager|solve|check|format", "content": "...", "timestamp": 0}
{"type": "citation", "citation": {"doc_id": "...", "page": 0, "section": "...", "node_id": "..."}}
{"type": "complete", "answer": "...", "citations": [...], "session_id": "...", "solve_dir": "..."}
{"type": "error", "error": "...", "message": "..."}
```

## VRAM Pressure Management

The system continuously monitors GPU memory (every 2s via pynvml) and reacts automatically:

| Level | VRAM Used | Action |
|-------|-----------|--------|
| GREEN | < 70% | All tiers available, T3 loads on-demand |
| YELLOW | 70–85% | Downgrade T3 KV cache, reduce T2 context by 50% |
| ORANGE | 85–93% | Unload T3, route generation to T2, reduce T1 concurrency |
| RED | > 93% | Emergency: unload T2, T1-only with 2K token truncation |

**Fallback cascade:** T3 → T2 (8B) → T2 (4B) → T1 (1.7B) → T1 (0.6B) → Error

## TurboQuant KV Cache Integration

Three implementation tiers, auto-detected at startup (FR-8.3):

1. **Tier 1 (Preferred):** LM Studio native via llama.cpp `--cache-type-k`/`--cache-type-v` flags with `q4_0`/`q8_0` types
2. **Tier 2 (Fallback):** `turboquant-server` (pip install) as OpenAI-compatible proxy with built-in KV compression
3. **Tier 3 (Advanced):** Application-layer Python using `TurboQuantCache` with HuggingFace Transformers

**Important:** TurboQuant-specific cache types (`turbo3`, `turbo4`) are NOT confirmed in LM Studio as of March 2026. The system uses llama.cpp's existing `q4_0`/`q8_0` today, upgrading automatically when native support arrives.

**Asymmetric KV quantization per tier:** Keys need higher precision than values. T1 uses `q4_0/q4_0`, T2 uses `K:q8_0/V:q4_0` (optimal tradeoff: 59% memory reduction, 0.86% perplexity loss), T3 uses `q8_0/q8_0` for maximum quality.

## Model Switching Logic

The Complexity Scorer routes queries to appropriate tiers using four weighted signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Query Complexity | 0.35 | Token count, comparison/reasoning keywords, multi-part detection |
| Document Size | 0.25 | Total pages, total tokens in retrieved chunks |
| Retrieved Chunk Count | 0.15 | Chunks scoring above relevance threshold |
| Available VRAM | 0.25 | Current free VRAM from pynvml |

**Decision:** score < 0.3 → T1 (fast path) | 0.3–0.6 → T2 (balanced) | > 0.6 → T3 (quality path)

## Retrieval Pipeline

Four modes, selectable per query via `retrieval_pipeline` parameter:

- **tree** (default for single-doc) — PageIndex hierarchical tree search with LLM reasoning over document structure. Returns page-level citations.
- **hybrid** (for multi-doc breadth) — Vector similarity + keyword retrieval merged and ranked
- **naive** — Pure vector similarity search
- **combined** — Tree search for precision + vector search for recall, results merged and deduplicated

## Performance Targets

| Metric | Target |
|--------|--------|
| PageIndex tree generation | < 60s for 100-page document |
| Vector KB creation | < 120s for 300 pages |
| TTFT (Smart Solver) | < 3s from query to first streamed token |
| PageIndex tree search | < 5s per retrieval |
| Token throughput (TurboQuant) | ≥ 15 tok/s on RTX 3090/4090 at 8K+ context |
| WebSocket streaming | < 100ms agent-to-frontend |
| RAGAS Faithfulness | ≥ 0.85 |
| Retrieval Precision@5 | ≥ 90% |

## Benchmarking Framework

Four test categories with FastAPI instrumentation (7 OpenTelemetry spans):

- **Category A:** End-to-end document Q&A latency (simple factual → multi-doc synthesis)
- **Category B:** KV cache memory efficiency (f16 baseline vs q8_0 vs q4_0 vs split)
- **Category C:** Answer quality and relevance (RAGAS faithfulness/relevancy, retrieval precision/recall)
- **Category D:** Throughput under concurrent load (1/3/10 users, burst load, sustained switching)

Trigger via `POST /api/v1/metrics/benchmarks/run`, poll with `GET /api/v1/metrics/benchmarks/{run_id}`.

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `LLM_MODEL` | Yes | — | Primary LLM model for LM Studio |
| `LLM_API_KEY` | Yes | — | LM Studio API key |
| `LLM_HOST` | Yes | — | LM Studio API endpoint URL |
| `EMBEDDING_MODEL` | Yes | — | Embedding model name |
| `EMBEDDING_API_KEY` | Yes | — | Embedding API key |
| `EMBEDDING_HOST` | Yes | — | Embedding API endpoint |
| `BACKEND_PORT` | No | 8001 | FastAPI backend port |
| `FRONTEND_PORT` | No | 3782 | React/Next.js frontend port |
| `SEARCH_PROVIDER` | No | perplexity | Web search provider (opt-in) |
| `SEARCH_API_KEY` | No | — | Search provider API key |
| `TURBOQUANT_ENABLED` | No | true | Enable KV cache quantization |
| `TURBOQUANT_BITS` | No | 4 | KV cache bit-width (3 or 4) |
| `TURBOQUANT_RESIDUAL_WINDOW` | No | 256 | Tokens kept in FP16 |
| `TURBOQUANT_TIER` | No | auto | Integration tier (1/2/3/auto) |
| `PAGEINDEX_MODEL` | No | (LLM_MODEL) | Model for tree generation |
| `PAGEINDEX_MAX_PAGES_PER_NODE` | No | 10 | Max pages per tree node |
| `PAGEINDEX_MAX_TOKENS_PER_NODE` | No | 20000 | Max tokens per tree node |
| `GPU_DEVICE_INDEX` | No | 0 | NVIDIA GPU device index |
| `VRAM_SAFETY_MARGIN_PCT` | No | 15 | Safety margin for VRAM estimates |
| `T2_TTL_SECONDS` | No | 600 | T2 model idle timeout |
| `T3_TTL_SECONDS` | No | 300 | T3 model idle timeout |

## Key Design Decisions

- **No external vector DB** — Uses DeepTutor's built-in embedding pipeline with local filesystem storage. No Milvus, Qdrant, etc.
- **Asymmetric KV quantization** — Keys get higher precision than values (community benchmarks show keys are more sensitive). Not from TurboQuant research; this is a system-level design choice.
- **Session-pinned LRU cache eviction** — Active Smart Solver sessions (max 2) pin their KV caches to prevent mid-pipeline eviction. All other caches use LRU.
- **Auto-detect TurboQuant tier at startup** — 5–10s detection probes LM Studio → turboquant-server → Python package → fallback to llama.cpp native q4_0/q8_0.
- **T2 default for PageIndex tree generation** — Batch operation, not latency-critical. T3 opt-in for complex academic papers.
- **Recursive character chunking (512 tok, 64 overlap)** as default for vector KB. Configurable per KB. Docling available as alternative RAG pipeline.
- **Single GPU (device index 0)** — Multi-GPU deferred to v2.
- **Web search is explicitly opt-in** — Core pipeline works fully offline. Web search requires `SEARCH_API_KEY` and `enable_web_search: true` per request.

## Assumptions to Verify

These are flagged in the architecture docs and should be validated during development:

| ID | Assumption | If Wrong |
|----|-----------|----------|
| A1 | LM Studio default API key is `"lm-studio"` | Auth failures — make configurable via env |
| A2 | LM Studio REST API at `/api/v0/models/load` works | Use `lms` CLI subprocess fallback |
| A3 | TurboQuant `turbo3`/`turbo4` NOT in LM Studio yet | Using llama.cpp `q4_0`/`q8_0` instead (4x vs theoretical 6x compression) |
| A6 | Qwen3-30B-A3B RAGAS faithfulness 0.91 (single source) | Run independent RAGAS evaluation in Phase 6 benchmarking |
| A8 | `turboquant-server` compatible with Qwen3 GGUF | Test during Phase 5; fall through to Tier 1 |
| A11 | LM Studio supports 4 concurrent parallel requests | Configurable semaphore limits |

## Out of Scope (v1.0)

- Cloud deployment / multi-user auth
- Fine-tuning or model training
- Real-time collaborative editing
- Mobile/tablet UI
- Non-English PageIndex tree generation
- Custom TurboQuant CUDA/Triton kernels
- External vector DB servers
- TurboQuant for embedding vector search
- Speculative decoding or other inference optimizations
- Production-grade secret management

## Reference Documents

- `01-product-requirements.md` — Full PRD with functional/non-functional requirements
- `02-system-architecture.md` — Technical architecture, OpenAPI spec, component interaction matrix, LM Studio integration layer
- `03-inference-strategy.md` — Multi-model inference, KV cache allocation, benchmarking harness, model switching, performance dashboard

## Source Repositories

- DeepTutor: [github.com/shinshekai/DeepTutor](https://github.com/shinshekai/DeepTutor)
- PageIndex: [github.com/shinshekai/PageIndex](https://github.com/shinshekai/PageIndex) (fork of [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex))
- TurboQuant paper: [arxiv.org/abs/2504.19874](https://arxiv.org/abs/2504.19874) (ICLR 2026)
