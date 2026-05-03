# UDIP Production Readiness Audit

**Date:** 2026-04-29  
**Auditor:** Claude Code  
**Scope:** Full-stack (Backend Python/FastAPI + Frontend React/Next.js 16+)  
**Verification Method:** Documentation review + code inspection + build/test execution

---

## Executive Summary

UDIP (Unified Document Intelligence Pipeline) has **implemented most features** listed in the PRD, but is **NOT production-ready**. The system has:

- ✅ **Backend core services implemented** — ModelManager, VRAMMonitor, LMStudioClient, BenchmarkRunner, all agent services
- ✅ **Frontend pages and components exist** — Dashboard, Solve, Documents, Knowledge, Models, Settings, Research, Guide, Questions
- ❌ **Frontend build BROKEN** — TypeScript error blocks production deployment
- ❌ **Backend tests FAILING** — 2 tests fail (tree_search, query endpoint)
- ❌ **Critical features are stubs** — TurboQuant not integrated, OpenTelemetry 1/7 points, RAGAS benchmarks return zeros
- ❌ **No frontend tests** — 0% coverage, no test files found

**Recommended Tier:** Fix-Critical-Only (MVP) — achievable in 5-8 hours of work.

---

## 1. Verification Evidence

| Check | Command Run | Result | Evidence |
|-------|--------------|--------|----------|
| Frontend build | `cd frontend && npm run build` | **FAILED** | Type error: `"outline"` not assignable to `Variant \| undefined` at `guide/page.tsx:206` |
| Backend tests | `cd backend && python -m pytest` | **2 FAILED** | `test_retrieve_with_tree_pipeline_returns_results` — `AttributeError: 'NoneType' object has no attribute 'check_health'` in `tree_search.py:126` |
| Backend tests (2nd) | (same) | **2 FAILED** | `test_query_http_returns_answer` — `assert 404 == 200` (endpoint returns 404) |
| Backend syntax | `python -m py_compile` on all `.py` | **PASSED** | Exit code 0 — no syntax errors |
| Frontend tests | `find frontend -name "*.test.*"` | **NONE FOUND** | No frontend test files exist |
| STATUS.md claim | "104 tests passed" | **FALSE** | Actual: 112 passed, **2 failed**, 1 skipped |

---

## 2. Issues Inventory

### CRITICAL (Must fix before any release)

| # | Issue | Root Cause | Impact | Components | Verified By |
|---|-------|-----------|--------|------------|---------------|
| **C1** | **Frontend build fails** — TypeScript error in `Badge` variant prop | `guide/page.tsx:206` passes `"outline"` but `Variant` type doesn't include it | Frontend cannot be deployed; Next.js production build exits with code 1 | `frontend/app/(platform)/guide/page.tsx` | `npm run build` exit code 1 |
| **C2** | **Backend tests failing: `tree_search.py` passes `None` as `lm_client`** | `TreeSearch.__init__` receives `None` for `lm_client` in test setup | 1 test fails with `AttributeError`; retrieval pipeline broken when LM Studio unavailable | `services/tree_search.py:126`, `test_retrieval.py` | `pytest` — FAILED test |
| **C3** | **Backend tests failing: `GET /api/v1/query` returns 404** | Route exists in `routers/retrieval.py` but returns 404 — likely import/routing issue | Core Q&A endpoint non-functional | `routers/retrieval.py`, `test_retrieval.py:99` | `pytest` — FAILED test |
| **C4** | **`config.py` `llm_host` defaults to empty string** | `llm_host: str = ""` — documented default is `"http://localhost:1234"` | Backend cannot connect to LM Studio without explicit env var; fallback `f"http://localhost:{settings.llm_port}"` only works if `llm_host` empty check | `app/config.py:9` | Code review |
| **C5** | **`model_manager.py` — `get_model_for_tier()` does NOT load models** | Method only returns already-loaded models; never calls `lm_client.load_model()` | Model tiers are non-functional — system can't proactively load T2/T3 on demand | `services/model_manager.py:68-74` | Code review + STATUS.md contradiction |

### HIGH (Fix before MVP)

| # | Issue | Root Cause | Impact | Components | Verified By |
|---|-------|-----------|--------|------------|---------------|
| **H1** | **`FALLBACK_CASCADE` uses different model names than `MODEL_TIERS`** | `FALLBACK_CASCADE` has `"qwen/qwen3.6-35b-a3b"` but documentation specifies Qwen3 models. Actual code has `"qwen/qwen3.6-35b-a3b"` matching `MODEL_TIERS[3]["models"]`. However, models don't match PRD's Qwen3-0.6B/1.7B/4B/8B/14B/30B-A3B | Fallback cascade may fail to find models; model names don't match PRD | `services/model_manager.py:18-25, 33-53` | Code review vs PRD |
| **H2** | **TurboQuant NOT actually integrated** | Code uses `q4_0`/`q8_0` from llama.cpp; no PolarQuant/QJL implementation exists; no `detect_turboquant_tier()` function in code | PRD/NFR claims 4-6x compression; actual is ~2x (q4_0 vs fp16). Assumption A3 documented but not reflected in STATUS.md as "incomplete" | `services/lm_studio_client.py`, `services/model_manager.py` | Code review vs `02-system-architecture.md` |
| **H3** | **OpenTelemetry 7-point instrumentation NOT implemented** | Only `benchmark_middleware` in `main.py` tracks `latency_ms`; no span creation for `pageindex.retrieve`, `lmstudio.inference`, `vram.monitor`, etc. | Observability gap — can't trace performance bottlenecks per PRD NFR-5 | `app/main.py:159-166` vs `02-system-architecture.md:1978-1988` | Code review |
| **H4** | **`handle_pressure()` for YELLOW only logs, doesn't act** | `model_manager.py:131-133` — logs "downgrading T3 KV cache" but never modifies `MODEL_TIERS` config or calls LM Studio to change cache types | VRAM pressure adaptation is non-functional; system won't downgrade cache or reduce T2 context under YELLOW | `services/model_manager.py:130-152` | Code review vs CLAUDE.md Section 7 |
| **H5** | **No frontend tests exist** | `find frontend -name "*.test.*"` returns nothing (only node_modules matches) | Can't verify frontend components work; regressions undetected | Frontend codebase | Verification command |
| **H6** | **Embedding model mismatch** | `config.py` sets `embedding_model = "text-embedding-qwen3-embedding-8b"` but PRD specifies Snowflake Arctic Embed M, nomic-embed-text-v1.5, or BGE-M3 | Embedding dimensions may not match vector store expectations; retrieval quality unverified | `app/config.py:15` vs `01-product-requirements.md:46-50` | Code review |
| **H7** | **Benchmark quality metrics are stubs** | `benchmark_runner.py:282-291` — all Category C (RAGAS faithfulness, precision, recall) return `value=0.0, passed=False` unconditionally | Performance targets (NFR-1.5, NFR-5.3-5.4) unverified | `services/benchmark_runner.py:268-293` | Code review |

### MEDIUM (Fix for production-ready tier)

| # | Issue | Root Cause | Impact | Components |
|---|-------|-----------|--------|------------|
| **M1** | **WebSocket `/ws/metrics` endpoint inefficient** — endpoint does `await asyncio.sleep(10)` in a loop; actual broadcast is in `_broadcast_loop()` lifespan task | Two separate async flows for one WS; connection may timeout; architecture is fragile | `app/main.py:254-268` |
| **M2** | **No authentication on WebSocket endpoints** | PRD says "WebSocket security: Authenticated WebSocket connections (implemented in DeepTutor v0.2.0)" but code has no auth check | Security gap — any local process can connect and trigger agent pipelines | `app/main.py:186, 254` |
| **M3** | **`pageindex_generator.py` at 91% coverage** — missing async integration tests | STATUS.md notes this but no plan to complete | Retrieval layer untested under real LM Studio conditions | `test_pageindex_generator.py` |
| **M4** | **`benchmark_runner.py` runs real LM calls without guarding for unavailable LM Studio** | `_run_category_latency()` calls `lm_client.stream_chat()` but benchmark may run without LM Studio; returns `value=-1` but doesn't fail gracefully | Benchmark results misleading; may report "passed=False" for infrastructure reasons | `services/benchmark_runner.py:171-211` |
| **M5** | **`text-embedding-qwen3-embedding-8b` model name** — Qwen3 embedding model may not exist in LM Studio's catalog | This is not a known model; typical embedding models are Snowflake, nomic, BGE. May fail at runtime | `app/config.py:15` |
| **M6** | **`llm_port` config exists but unused in client initialization** | `lm_studio_client.py:22` uses `settings.llm_host or f"http://localhost:{settings.llm_port}"` — but if `llm_host=""`, the `or` evaluates `""` as falsy and falls back to `localhost:1234`. This actually works, but is fragile | Subtle bug if `llm_host` is set to a whitespace string | `app/config.py:10`, `services/lm_studio_client.py:21-22` |

### LOW (Nice to have)

| # | Issue | Root Cause | Impact |
|---|-------|-----------|--------|
| **L1** | **STATUS.md claims `load_model`/`unload_model` are no-ops** — but code review shows they DO try REST API + CLI fallback | Documentation is outdated; STATUS.md says "Known Issues: LM Studio load_model/unload_model are no-ops" but `lm_studio_client.py:59-143` implements both | Developer confusion |
| **L2** | **No Docker deployment** — PRD FR-9.5 requires `docker-compose.yml` | Missing from codebase | Can't deploy via Docker |
| **L3** | **`pyproject.toml` not reviewed** — need to verify dependencies are complete | May be missing `pynvml`, `httpx`, `fastapi`, etc. | Deployment may fail |
| **L4** | **Frontend `.env` or `next.config.ts` may not set `BACKEND_PORT` correctly** | Frontend hardcoded to `localhost:8001` in `lib/websocket.ts:3` | Inflexible for deployment |

---

## 3. Remediation Plan

### Phase 1: Unblock Build (CRITICAL — Effort: 1 hour)

| Task | Fix | Success Criteria |
|------|-----|-------------------|
| **Fix C1** | Change `"outline"` to valid `Variant` value in `guide/page.tsx:206` (likely `"outline"` should be `"default"` or the Badge component needs prop update) | `npm run build` exits 0 |
| **Fix C2** | Fix `TreeSearch` to handle `None` lm_client gracefully OR fix test setup to provide mock | `pytest tests/test_retrieval.py::test_retrieve_with_tree_pipeline_returns_results` passes |
| **Fix C4** | Change `config.py:9` to `llm_host: str = "http://localhost:1234"` | Backend connects to LM Studio with default config |

### Phase 2: Core Functionality (CRITICAL — Effort: 4-6 hours)

| Task | Fix | Success Criteria |
|------|-----|-------------------|
| **Fix C3** | Debug why `GET /api/v1/query` returns 404 — likely import issue in `routers/retrieval.py` or route not registered | `pytest tests/test_retrieval.py::test_query_http_returns_answer` passes |
| **Fix C5** | Implement actual model loading in `get_model_for_tier()` — call `lm_client.load_model()` when no model loaded | Model tiers functional; integration test passes |
| **Verify H1** | Align model names in `FALLBACK_CASCADE` with `MODEL_TIERS` OR update PRD to reflect actual model choices | No name mismatches; fallback cascade works |

### Phase 3: Production Gaps (HIGH — Effort: 1-2 days)

| Task | Fix | Success Criteria |
|------|-----|-------------------|
| **Fix H4** | Implement actual VRAM pressure actions in `handle_pressure()` — modify `MODEL_TIERS` config, call LM Studio to apply changes | YELLOW/ORANGE/RED policies take effect (testable) |
| **Fix H2** | Document TurboQuant gap: add banner in UI when Tier 1 with basic q4_0; update STATUS.md to reflect "TurboQuant NOT integrated" | Users informed of 2x (not 6x) compression |
| **Fix H3** | Implement OpenTelemetry spans: `pageindex.retrieve`, `lmstudio.inference`, `vram.monitor` at minimum | 7 instrumentation points from spec have corresponding code |
| **Fix H5** | Add frontend tests for critical paths: Solve page, Dashboard, Document upload | ≥60% frontend code coverage |
| **Fix H6** | Change `embedding_model` default to `"Snowflake/snowflake-arctic-embed-m-gguf"` per PRD | Embedding model matches documentation |
| **Fix H7** | Implement RAGAS evaluation in `benchmark_runner.py` Category C OR mark as "requires LM Studio + eval dataset" | Quality metrics are real values, not 0.0 |

### Phase 4: MVP Polish (MEDIUM — Effort: 2-3 days)

| Task | Fix | Success Criteria |
|------|-----|-------------------|
| **Fix M2** | Add WebSocket auth token validation (at minimum, check for dev token or localhost-only) | Unauthorized WS connections rejected |
| **Fix M3** | Complete `test_pageindex_generator.py` async integration tests | 100% coverage for that file |
| **Fix M1** | Refactor WS metrics to use single clean pattern (either lifespan broadcast OR endpoint loop) | Code is maintainable |

---

## 4. Release Readiness Checklist

### Test Coverage and Quality Gates

| Gate | Target | Current State | Status |
|------|--------|---------------|--------|
| Backend unit tests pass | 0 failures | **2 FAILED** (tree_search, query endpoint) | ❌ BLOCKING |
| Backend coverage | ≥80% | ~95% (individual files high; 2 failures drag score) | ⚠️ MOSTLY PASS |
| Frontend build | Exit 0 | **Exit 1** (TypeScript error) | ❌ BLOCKING |
| Frontend tests | ≥60% coverage | **0%** (no tests exist) | ❌ BLOCKING |
| Integration tests | All agent pipelines | Smart Solver: ✅ via WebSocket; others: untested end-to-end | ⚠️ PARTIAL |

### Performance Benchmarks

| Metric | Target | Current State | Status |
|---------|--------|---------------|--------|
| TTFT < 3s | PRD NFR-1.3 | Untested (benchmark returns -1 when LM Studio unavailable) | ❌ UNVERIFIED |
| Token throughput ≥15 tok/s | PRD NFR-1.5 | Untested (Category D runs but metrics are response_time, not tok/s) | ❌ UNVERIFIED |
| PageIndex generation <60s/100pp | PRD NFR-1.1 | Test exists but async integration at 91% coverage | ⚠️ PARTIAL |
| RAGAS Faithfulness ≥0.85 | PRD NFR-5.3 | **Stub — returns 0.0, passed=False** | ❌ NOT IMPLEMENTED |
| Retrieval Precision@5 ≥90% | PRD NFR-5.3 | **Stub — returns 0.0, passed=False** | ❌ NOT IMPLEMENTED |

### Security Requirements

| Requirement | Target | Current State | Status |
|--------------|--------|---------------|--------|
| WebSocket auth | PRD: "Authenticated WebSocket" | **No auth check** on any WS endpoint | ❌ NOT IMPLEMENTED |
| Local-first enforced | PRD NFR-3.1 | Web search is opt-in; core is local ✅ | ✅ PASS |
| Code execution sandboxing | PRD OQ-10 | DeepTutor has code execution; sandboxing unverified | ⚠️ UNVERIFIED |
| CORS config | Secure origins | Allows `localhost:3782` and `localhost:3000` ✅ (dev-only) | ✅ PASS (dev) |

### Operational Procedures

| Requirement | Target | Current State | Status |
|--------------|--------|---------------|--------|
| OpenTelemetry 7 points | PRD NFR-5.1 | **Only 1 implemented** (middleware timing) | ❌ 1/7 IMPLEMENTED |
| TurboQuant integration | PRD FR-8 | **Not integrated** — using basic q4_0/q8_0 | ❌ NOT IMPLEMENTED |
| Docker deployment | PRD FR-9.5 | **No docker-compose.yml** found | ❌ NOT IMPLEMENTED |
| Health check endpoint | PRD `/api/v1/health` | ✅ Implemented and functional | ✅ PASS |
| Configurable via env vars | PRD Appendix A | ✅ Most vars supported; `llm_host` default wrong | ⚠️ MOSTLY PASS |

---

## 5. Risk Assessment — Known Unknowns

| Risk | Impact | Current Mitigation | Verified? |
|------|--------|-------------------|----------|
| **TurboQuant integration status** — llama.cpp `q4_0`/`q8_0` only (2x compression, not 6x) | Performance: token throughput may be 2x lower than PRD claims | Documented as Assumption A3; UI should show "Basic KV quantization" not "TurboQuant" | ⚠️ DOCUMENTED BUT NOT REFLECTED IN UI |
| **LM Studio API reliability** — `/api/v0/models/load` endpoint unverified | Model loading may fail silently | Fallback to `lms` CLI implemented | ⚠️ UNTESTED |
| **Consumer GPU VRAM constraints** — 16GB GPU may not fit T3 (18GB) + T2 (5.5GB) + T1 (1.2GB) | System may never load T3; fallback cascade to T2 | VRAM monitor implemented; fallback cascade coded but untested | ⚠️ UNTESTED |
| **RAGAS benchmarks accuracy** — Qwen3-30B-A3B faithfulness 0.91 from single source | Quality ceiling may be lower than expected | Independent evaluation needed (Category C stubbed) | ❌ NOT IMPLEMENTED |
| **PageIndex tree generation quality** — benchmarked with gpt-4o, not local 7B-8B models | Tree quality may degrade with smaller local models | Benchmark with local models recommended (OQ-3) | ❌ NOT TESTED |
| **Frontend WebSocket stability** — `WebSocketManager` has reconnect logic but no integration test | Metrics WS may disconnect silently; Solve WS may drop during long generations | Reconnect logic exists (10 attempts max) | ⚠️ UNTESTED |
| **`FALLBACK_CASCADE` model name mismatch** — names differ from `MODEL_TIERS` | Fallback may fail to find a working model | Names appear to match on review, but model IDs don't match PRD's Qwen3 tiers | ⚠️ MISALIGNED WITH PRD |

---

## 6. Readiness Tier Determination

| Tier | Criteria | UDIP Status |
|------|----------|--------------|
| **Production-ready** | Comprehensive tests, error handling, docs, monitoring | ❌ **NOT ACHIEVABLE** — 2 critical build/test failures, no frontend tests, OpenTelemetry incomplete, TurboQuant not integrated |
| **Solid implementation** | Good practices, core functionality tested | ⚠️ **PARTIALLY** — backend core works (when tests pass), but frontend build fails, VRAM pressure actions are no-ops, embedding model is wrong |
| **Fix critical issues only** | Minimal changes to reach MVP | ✅ **ACHIEVABLE** — fix C1 (frontend build), C2 (tree_search NoneType), C3 (query 404), C4 (llm_host default), C5 (model loading) → MVP with known limitations |

### Recommended Path to Production-Ready

```
TODAY (Critical Fixes):
  ├── Fix frontend TypeScript error (C1) → Build passes
  ├── Fix tree_search.py NoneType (C2) → Retrieval tests pass
  ├── Fix query endpoint 404 (C3) → Core Q&A works
  ├── Fix llm_host default (C4) → Connects with defaults
  └── Implement model loading in get_model_for_tier (C5) → Tiers work

THIS WEEK (High Fixes):
  ├── Implement VRAM pressure actions (H4)
  ├── Document TurboQuant gap (H2) → Set correct expectations
  ├── Add OpenTelemetry spans (H3) → Observability
  ├── Fix embedding model (H6) → Match PRD
  └── Stub RAGAS benchmarks (H7) → Quality verifiable

NEXT SPRINT (Medium):
  ├── Add frontend tests (H5)
  ├── WebSocket auth (M2)
  └── Complete PageIndex integration tests (M3)
```

---

## 7. Summary

**Current State: NOT PRODUCTION READY** — 5 critical issues, frontend build broken, 2 backend tests failing, core features (TurboQuant, OpenTelemetry, RAGAS benchmarks) are stubs or missing.

**Quickest path to MVP (fix-critical-only):** 5-8 hours of work to fix C1-C5 → functional system with known limitations (no TurboQuant, basic observability).

**Path to Production-Ready:** 2-3 weeks to address all High and Medium issues, add frontend tests, implement actual TurboQuant or document the gap, and achieve ≥80% test coverage on both frontend and backend.

---

## Appendix A: File Reference

### Backend Key Files
- `backend/app/config.py` — Settings with env vars (C4, H6)
- `backend/app/main.py` — FastAPI entry, lifespan, WebSocket endpoints (M1, M2)
- `backend/app/services/model_manager.py` — Tiers, fallback cascade (C5, H1, H4)
- `backend/app/services/lm_studio_client.py` — HTTP client, load/unload (H2)
- `backend/app/services/vram_monitor.py` — GPU polling (H3)
- `backend/app/services/benchmark_runner.py` — Categories A-D (H7)
- `backend/app/routers/system.py` — Health, config, models, VRAM, cache, metrics
- `backend/app/routers/retrieval.py` — Retrieve, query endpoints (C3)
- `backend/app/services/tree_search.py` — Tree search (C2)

### Frontend Key Files
- `frontend/app/(platform)/guide/page.tsx` — TypeScript error (C1)
- `frontend/lib/websocket.ts` — WebSocket manager, REST helpers
- `frontend/app/(platform)/solve/page.tsx` — Smart Solver UI
- `frontend/app/(platform)/dashboard/page.tsx` — Dashboard
- `frontend/components/dashboard/global-resource-monitor.tsx` — VRAM gauge
- `frontend/components/dashboard/inference-throughput-grid.tsx` — Throughput metrics

### Documentation
- `docs/01-product-requirements.md` — PRD with functional/non-functional requirements
- `docs/02-system-architecture.md` — Technical architecture, OpenAPI spec
- `docs/03-inference-strategy.md` — Multi-model inference, KV cache, benchmarking
- `docs/superpowers/STATUS.md` — Implementation status (contains outdated claims)
- `CLAUDE.md` — Project overview, architecture, API endpoints

---

*Report generated: 2026-04-29 by Claude Code*  
*Verification: Build/test commands executed and output captured*
