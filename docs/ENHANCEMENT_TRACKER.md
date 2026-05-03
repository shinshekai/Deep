# UDIP Enhancement Tracker

**Created:** 2026-05-03  
**Status:** COMPLETE  

---

## Phase 0: Critical Bug Fixes (Immediate)

- [x] **0.1** Delete duplicate stub `/query` and `/retrieve` routes from `agent.py:15-22` (C1)
- [x] **0.2** Add zip-slip path-traversal protection to `document_processor.py` archive extraction (C4)
- [x] **0.3** Replace bare `except:` with typed exceptions in `document_processor.py` (M6)
- [x] **0.4** Fix `websocket.ts` hardcoded URLs — use `config.ts` env vars (H5)
- [x] **0.5** Fix Docker port mismatch — align `docker-compose.yml` to port 8001 (H8)
- [x] **0.6 (Reverted to TurboQuant per user)** Rename `turboquant_*` config fields to `kv_cache_*` for honest labeling (H2)

## Phase 1: Security & Stability

- [x] **1.1** Wire `handle_pressure()` ORANGE/RED to call `lm_client.unload_model()` (C3)
- [x] **1.2** Implement YELLOW pressure: reload model with downgraded KV cache params (C3)
- [x] **1.3** Fix `DeepResearchService` singleton — move to `app.state` (M5)
- [x] **1.4** Fix `text_extractor.py` sync/async mismatch (M2)
- [x] **1.5** Wire real VRAM + doc count into `solve_orchestrator.py` complexity scoring (M3)

## Phase 2: Test Coverage

- [x] **2.1** Add tests for PPTX extractor
- [x] **2.2** Add tests for HTML extractor
- [x] **2.3** Add tests for ODT extractor
- [x] **2.4** Add tests for RTF extractor
- [x] **2.5** Add tests for EPUB extractor
- [x] **2.6** Add tests for email (.msg/.eml) extractor
- [x] **2.7** Add tests for archive (.zip) extractor with zip-slip check
- [x] **2.8** Add tests for spreadsheet (.csv/.xlsx) extractor
- [x] **2.9** Add tests for image OCR extractor
- [x] **2.10** Add tests for code file extractor (.py/.js etc.)
- [x] **2.11** Add router integration tests for `agent.py`
- [x] **2.12** Add router integration tests for `knowledge.py`
- [x] **2.13** Target: overall backend coverage ≥ 80%

## Phase 3: RecursiveMAS Integration — Recursive Solve Pipeline

- [x] **3.1** Create `app/services/recursive_solver.py` — core recursive agent framework
- [x] **3.2** Implement Sequential pattern: Planner → Critic → Solver with recursion rounds
- [x] **3.3** Implement convergence detection (embedding similarity between rounds)
- [x] **3.4** Implement compressed context transfer (200-token summaries between agents)
- [x] **3.5** Integrate recursive solver into `solve_orchestrator.py` as alternative mode
- [x] **3.6** Add `recursive` mode to WebSocket `/api/v1/solve` handler
- [x] **3.7** Implement Deliberation pattern: Reflector ↔ Tool-Caller recursive loop
- [x] **3.8** Implement Mixture pattern: domain-specialized parallel agents + summarizer
- [x] **3.9** Add collaboration pattern selection to `query_router.py` / complexity scorer
- [x] **3.10** Add tests for recursive solver (convergence, pattern selection, round limits)

## Phase 4: ARA Integration — Knowledge Artifacts

- [x] **4.1** Create `app/services/ara_compiler.py` — ARA artifact generation service
- [x] **4.2** Implement Logic Layer extraction (claims, concepts, experiments)
- [x] **4.3** Implement Solution Layer extraction (architecture, heuristics, constraints)
- [x] **4.4** Implement Trace Layer (exploration DAG with dead-end preservation)
- [x] **4.5** Add ARA storage structure under `data/knowledge_bases/{kb}/ara/{doc}/`
- [x] **4.6** Wire ARA compilation into knowledge upload pipeline (`routers/knowledge.py`)
- [x] **4.7** Implement ARA search API (`search_claims()`, `search_heuristics()`)
- [x] **4.8** Add `"ara"` retrieval pipeline mode to `retrieval.py`
- [x] **4.9** Add provenance tagging to content creation outputs
- [x] **4.10** Implement exploration trace recorder in `solve_orchestrator.py`
- [x] **4.11** Implement ARA Rigor Reviewer as quality benchmark (replaces RAGAS stubs)
- [x] **4.12** Add tests for ARA compiler and retrieval

## Phase 5: Operational Hardening

- [x] **5.1 (TurboQuant Asymmetric K/V integration)** Implement proactive model loading in `get_model_for_tier()` (C2)
- [x] **5.2** Add OpenTelemetry custom spans to core services (H3)
- [x] **5.3** Create `backend/Dockerfile` and `frontend/Dockerfile` (M7)
- [x] **5.4** Add WebSocket authentication (H4)
- [x] **5.5** Update STATUS.md with current state (L1)
- [x] **5.6** Add frontend tests for Solve, Dashboard, WebSocket (H7)

---

## Progress Summary

| Phase | Total | Done | Status |
|-------|-------|------|--------|
| 0 — Critical Fixes | 6 | 6 | ✅ Complete |
| 1 — Security & Stability | 5 | 5 | ✅ Complete |
| 2 — Test Coverage | 13 | 13 | ✅ Complete |
| 3 — RecursiveMAS | 10 | 10 | ✅ Complete |
| 4 — ARA Integration | 12 | 12 | ✅ Complete |
| 5 — Operational | 6 | 6 | ✅ Complete |
| **TOTAL** | **52** | **52** | **100%** |
