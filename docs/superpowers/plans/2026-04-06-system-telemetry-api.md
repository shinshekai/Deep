# Phase 5–7: System Telemetry & Backend API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform stub system routes into fully functional APIs connecting to real services (VRAM Monitor, Model Manager, LM Studio, Benchmark Runner), and wire them to the existing React dashboard components.

**Scope:** Backend REST endpoints only. Frontend components already exist and consume these endpoints.

---

## Current Status

| Route | Status | Details |
|-------|--------|---------|
| `GET /api/v1/health` | Stub | Returns hardcoded False for LM/GPU |
| `GET/PUT /api/v1/config` | Partial | GET reads settings; PUT is no-op |
| `GET /api/v1/models` | Stub | Returns `[]` |
| `POST /api/v1/models/{id}/load` | Stub | Returns fake loading status |
| `POST /api/v1/models/{id}/unload` | Stub | Returns fake unloaded status |
| `GET /api/v1/vram/status` | Stub | Returns zeroed-out JSON |
| `GET /api/v1/cache/status` | Stub | Returns `{models: {}}` |
| `PUT /api/v1/cache/config` | Stub | No-op |
| `POST /api/v1/cache/evict` | Stub | No-op |
| `GET /api/v1/metrics/history` | Partial | Returns in-memory list |
| `POST /api/v1/metrics/benchmarks/run` | Stub | Returns fake run_id |
| `GET /api/v1/metrics/benchmarks/{run_id}` | Stub | Returns pending |

## Working Services

| Service | Status | Notes |
|---------|--------|-------|
| VRAMMonitor | ✅ Working | 2s poll, on_update callbacks, GREEN/YELLOW/ORANGE/RED |
| LMStudioClient | ✅ Working | health, list_models, stream_chat |
| ModelManager | ✅ Working | Tier configs, TTL eviction, fallback |
| PageIndexTreeGenerator | ✅ Working | 3-pass pipeline, all tests pass |
| Complexity Scorer | ✅ Working | 4-signal weighted scoring |

## Missing Services

| Service | Needed By | Notes |
|---------|-----------|-------|
| BenchmarkRunner | `/benchmarks/run`, `/benchmarks/{run_id}` | Categories A-D test runner |
| Cache Manager | `/cache/*` | Manages KV cache state |
| System Registry | `/health`, `/models`, `/vram` | Central state store |

---

### Task 1: Wire system routes to real services (non-benchmark)

**Goal:** Replace stub implementations in `system.py` with real calls to existing services.

**Files:**
- Modify: `backend/app/routers/system.py` (complete rewrite)
- Modify: `backend/app/main.py` (pass services to routes)

**Steps:**

- [ ] **Step 1: Add system router access to global services**

In `main.py`, the routers are imported at module level but have no access to `vram_monitor`, `model_manager`, or `lm_client`. Convert `system.py` from standalone to dependency-injection pattern. Replace the static import with a dependency that accesses globals from `main` via `FastAPI.depends` or a shared state registry.

Approach: Create a simple `AppState` class in `main.py` that holds all services, and use it via a `get_state` dependency function. This keeps routes testable and avoids circular imports.

- [ ] **Step 2: Implement real `/health` endpoint**

```
GET /api/v1/health
```

- Call `lm_client.check_health()` for LM Studio status
- Call `vram_monitor.get_status()` for GPU status
- Return `turboquant` config from settings
- Calculate uptime from startup timestamp

- [ ] **Step 3: Implement real `/models` endpoints**

```
GET /api/v1/models
POST /api/v1/models/{model_id}/load
POST /api/v1/models/{model_id}/unload
```

- GET: Call `lm_client.list_models()` and enrich with `model_manager._loaded_models` data, tier assignments, and TTL info
- POST load: Call `model_manager.load_model()` and return real status
- POST unload: Call `model_manager.unload_model()` and return real status

- [ ] **Step 4: Implement real `/vram/status` endpoint**

```
GET /api/v1/vram/status
```

- Read from `vram_monitor` latest state
- Return per spec: `total_mb`, `used_mb`, `free_mb`, `utilization_pct`, `pressure_level`, `breakdown`

- [ ] **Step 5: Implement real `/cache/*` endpoints**

```
GET /api/v1/cache/status
PUT /api/v1/cache/config
POST /api/v1/cache/evict
```

- Build a simple `CacheState` registry that tracks per-model KV cache type, context usage, and size estimates
- GET: Return turboquant config + per-model cache info from state
- PUT: Update settings, return new config
- POST: Clear cache state entries, return freed estimate

- [ ] **Step 6: Implement real `/config` PUT endpoint**

```
PUT /api/v1/config
```

- Accept body fields matching OpenAPI `SystemConfigUpdate` schema
- Only provided fields updated; use Python `setattr` on settings dict
- Persist to `.env` file or in-memory override
- Return updated config

- [ ] **Step 7: Run tests**

```bash
cd backend && python -c "from app.routers.system import router; print('import OK')"
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/routers/system.py
git commit -m "feat: wire system routes to real services

- /health: real LM Studio + GPU status
- /models: backed by ModelManager + LM Studio
- /vram/status: backed by VRAMMonitor
- /cache/*: simple registry-based KV cache state tracking
- /config: PUT updates settings at runtime"
```

---

### Task 2: Benchmark Runner service

**Goal:** Implement categories A-D benchmark harness from `03-inference-strategy.md`, backing `/metrics/benchmarks/run` and `/metrics/benchmarks/{run_id}`.

**Files:**
- Create: `backend/app/services/benchmark_runner.py` (~200 lines)
- Modify: `backend/app/routers/system.py` (use real benchmark runner)
- Create: `backend/tests/test_benchmark_runner.py`

**Benchmark Categories from spec:**

| Category | Tests | Method |
|----------|-------|--------|
| A — Latency | 5 tests | End-to-end Q&A timing: simple, multi-chunk, needle, multi-doc, fast-path |
| B — KV efficiency | 6 tests | Memory measurements across quantization modes |
| C — Quality | 6 tests | RAGAS faithfulness/relevancy, retrieval precision/recall |
| D — Throughput | 5 tests | Concurrent load: 1/3/10 users, burst, sustained |

**Steps:**

- [ ] **Step 1: Create benchmark runner service**

Create `backend/app/services/benchmark_runner.py`:

- `BenchmarkRunner` class with async `run(test_id) -> BenchmarkResult`
- Each category is a separate `run_category_*()` method
- Results stored in `_runs: dict[str, BenchmarkRun]` with status, progress, results
- Background task processes runs sequentially

```python
@dataclass
class BenchmarkResult:
    test_id: str
    category: str  # "latency", "kv_cache", "quality", "throughput"
    test_case: str
    metric: str
    value: float
    threshold: float
    passed: bool

@dataclass
class BenchmarkRun:
    run_id: str
    status: str  # "running", "completed", "failed"
    progress_pct: int
    results: list[BenchmarkResult]
    started_at: float
    completed_at: float | None = None
```

- [ ] **Step 2: Wire to system.py routes**

- Replace stub `/metrics/benchmarks/run` with `benchmark_runner.start_run()`
- Replace stub `/metrics/benchmarks/{run_id}` with `benchmark_runner.get_run(run_id)`
- Add `GET /metrics/benchmarks/latest` → return most recent completed run

- [ ] **Step 3: Write benchmark runner tests**

Create `backend/tests/test_benchmark_runner.py`:
- Test individual test case execution (mock LM client)
- Test run lifecycle (start → poll → complete)
- Test result aggregation
- Test error handling (failed test, unreachable LM Studio)

- [ ] **Step 4: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/benchmark_runner.py backend/app/routers/system.py backend/tests/test_benchmark_runner.py
git commit -m "feat: implement benchmark runner service

- Categories A-D: latency, KV efficiency, quality, throughput
- Async background execution with polling
- Test suite with mock LM client"
```

---

### Task 3: Add retrieval + query + document deletion endpoints

**Goal:** Implement `POST /api/v1/retrieve`, `POST /api/v1/query`, and `DELETE /knowledge/bases/{kb}/documents/{doc_id}` per OpenAPI spec.

**Files:**
- Create: `backend/app/routers/retrieval.py` (retrieve + query endpoints)
- Create: `backend/app/services/query_router.py`
- Create: `backend/app/services/hybrid_rag.py`
- Modify: `backend/app/routers/knowledge.py` (add document DELETE)
- Create: `backend/tests/test_retrieval.py`

**Steps:**

- [ ] **Step 1: Create query router service**

`backend/app/services/query_router.py` — lightweight classifier that selects retrieval mode:
- If query is specific + has doc_id → tree search
- If query is broad → hybrid search
- If `retrieval_pipeline` is explicitly set → use that mode

- [ ] **Step 2: Create hybrid RAG service**

`backend/app/services/hybrid_rag.py` — stub for now:
- Reads vector KB files from `data/knowledge_bases/{kb_name}/vectors/`
- Since vector KB builder doesn't exist yet, return empty results with a warning
- Implement the merge/dedup logic for when vector search returns results later

- [ ] **Step 3: Create retrieval router**

`backend/app/routers/retrieval.py`:

POST `/api/v1/retrieve`:
- Body: `{query, kb_name, doc_id?, pipeline?, top_k?, min_relevance_score?}`
- Route to PageIndex tree search or hybrid RAG based on pipeline
- Return `RetrievalResponse`: `query`, `pipeline_used`, `results[]`, `retrieval_latency_ms`, `model_tier_used`, `total_candidates_scored`

POST `/api/v1/query` (HTTP Q&A fallback):
- Body: `{query, kb_name, mode?, retrieval_pipeline?, session_id?}`
- Non-streaming HTTP equivalent of the Smart Solver WS
- Calls retrieval → complexity scoring → LLM → returns complete answer
- Return `QueryResponse`: `answer`, `citations`, `agent_steps`, `model_tier_used`, `complexity_score`, `e2e_latency_ms`, `session_id`, `solve_dir`

- [ ] **Step 4: Add document deletion to knowledge router**

Add to `backend/app/routers/knowledge.py`:

DELETE `/api/v1/knowledge/bases/{kb_name}/documents/{doc_id}`:
- Remove tree JSON from `pageindex/` directory
- Remove raw upload file
- Update KB registry counts
- Return 204 on success, 404 if files don't exist

- [ ] **Step 5: Wire to main.py**

- Add `app.include_router(retrieval_router)`
- Register router in lifespan

- [ ] **Step 6: Write tests**

`backend/tests/test_retrieval.py`:
- Test retrieval endpoint with various pipeline modes
- Test query router mode selection
- Test empty KB returns zero results gracefully
- Test HTTP query endpoint returns structured response
- Test document deletion removes files and updates registry

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/retrieval.py backend/app/routers/knowledge.py backend/app/services/query_router.py backend/app/services/hybrid_rag.py backend/tests/test_retrieval.py
git commit -m "feat: add retrieval, HTTP query, and document deletion endpoints

- POST /retrieve: tree search + hybrid RAG routing
- POST /query: non-streaming HTTP Q&A fallback
- DELETE /knowledge/bases/{kb}/documents/{doc}: doc removal + cleanup"
```

---

### Task 4: Integration verification

**Goal:** Smoke test all new endpoints end-to-end.

**Steps:**

- [ ] **Step 1: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v
```

- [ ] **Step 2: Start backend**

```bash
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- [ ] **Step 3: Smoke test each endpoint**

```bash
curl http://localhost:8001/api/v1/health
curl http://localhost:8001/api/v1/vram/status
curl http://localhost:8001/api/v1/models
curl http://localhost:8001/api/v1/cache/status
curl -X POST http://localhost:8001/api/v1/metrics/benchmarks/run
```

- [ ] **Step 4: Commit final status**

```bash
git add backend/tests/ backend/app/
git commit -m "chore: smoke test all system endpoints end-to-end"
```

---

### Non-Goals (Deferred to Future Plans)

| Item | Reason | Future Plan |
|------|--------|-------------|
| Vector KB Builder (embedding pipeline) | Requires LM Studio embedding + chunking + file storage; FR-1.3 | Separate plan needed |
| Numbered Item Extractor | FR-1.5, optional extraction | Separate plan needed |
| Smart Solver full dual-loop (agents) | FR-3, currently has basic WS only | Separate plan needed |
| Question Generator (custom + exam mimicry) | FR-4, full UI backend exists | Separate plan needed |
| Guided Learning (4-agent flow) | FR-5, full UI backend exists | Separate plan needed |
| Deep Research (3-phase pipeline) | FR-6, full UI backend exists | Separate plan needed |
| PriorityQueue with semaphore management | Phase 8 from implementation sequence; current semaphores in LM Studio are sufficient for now | Future optimization |
| OpenTelemetry spans (7 instrumentation points) | Nice-to-have observability; dashboard works without it | Phase 9 |
| Docling parser integration | PyMuPDF works; Docling is opt-in alternative | Future enhancement |
