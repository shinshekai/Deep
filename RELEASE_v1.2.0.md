# Release v1.2.0 — Production Excellence

**Tag:** `v1.2.0`
**Date:** 2026-06-09
**Commits since v1.1.2:** 37

---

## Highlights

This is the **Production Excellence** release — the culmination of a 10-agent security audit, a 7-phase quality execution plan, and a full research alignment validation. DEEP now ships with 556 backend tests (0 mocks), 38+ services, 14 memory tables, and production-grade Docker deployments.

---

## What's New

### Knowledge Graph (`knowledge_graph.py`)
- Entity-relation graph for dual-index RAG (KG + Dense Embeddings)
- SQLite-backed with `get_knowledge_graph()` singleton
- Enables graph-based retrieval alongside vector search

### Progressive Crystallization (`memory_service.py`)
- Observations staged in `staged_observations` table before permanent storage
- `stage_observation()` → `crystallize_observations()` pipeline
- Closure signals trigger promotion to facts

### Contract Testing (`test_contract.py`)
- 6 frontend/backend API schema validation tests
- Ensures type safety across the full stack
- Documents actual API shapes (lm_studio as bool, turboquant_bits as int)

### Property-Based Testing (`test_property_based.py`)
- 9 Hypothesis-powered tests for data transformations
- Security invariants, prompt registry, memory operations
- Randomized input generation for edge case discovery

### Locust Load Testing (`locust_load.py`)
- Production load testing with Locust
- 50 concurrent users, 10 requests/sec
- Renamed from `test_load.py` to avoid pytest recursion

### User-Configurable `enable_thinking`
- New toggle in Settings page (`settings/page.tsx`)
- Config field in `config.py`: `enable_thinking: bool = False`
- Resolves from user settings when not explicitly set

---

## What's Fixed

### Security (3 fixes)
- **lxml CVE-2026-41066 (High XXE)** — Upgraded 5.4.0 → 6.1.0
- **WebSocket auth hardened** — First-message auth (token sent as JSON, not URL query param)
- **Token endpoint requires Bearer auth** — H8 fix

### Memory System (8 fixes)
- **C1**: `batch_resolve_contradictions` uses shared DB connection
- **C2**: `update_episode_rating()` method + richer compaction summaries
- **C3**: Contradiction resolution returns candidates for user confirmation
- **H5**: Compaction summaries include outcome_rating and answer snippets
- **L2**: `_store_chunks` validates against `VALID_CHUNK_TABLES`
- **L4**: `recall_facts` uses 2-phase read+write (minimal lock)
- **L5**: `compact_episodes` INSERT includes `provenance` column
- **DB-4-017**: Deterministic recall ordering (`best_rank, created_at DESC, id`)

### Performance (5 fixes)
- **M5**: Complexity routing activates — `retrieval_pipeline` defaults to `None`
- **M6**: Response cache uses absolute resolved path (`Path.resolve()`)
- **M7**: Response cache singleton uses `threading.Lock` for init
- **H3**: RRF k=60 constant from Cormack et al. 2009 paper
- **H7**: Deduplicated VRAM telemetry (flat variables, no useMemo)

### Agent System (4 fixes)
- **A2**: Verification-as-invariant in solve pipeline
- **A3**: L3 cross-surface synthesis (4 slots: profile/recent/scope/preferences)
- **A4**: Dead-end tracking with prevention queries
- **A5**: Provenance tracking with audit trail

### Frontend (3 fixes)
- **C6**: ChatMessageList bottomRef fix
- **C7**: Chat page refs for streaming
- **L9**: Sparkline gradient uses `useId()` (no collision)

### Infrastructure (5 fixes)
- **M1**: `is_available` checks `llm_client.is_connected` state
- **M4**: Retrieval precision uses actual precision@k
- **SEC-5-007**: `is_keyring_available()` has 5-minute time-based cache
- **Task WAL**: Write-ahead log for crash recovery
- **Model tiers**: T1: gemma-4-e2b/e4b, T2: qwen3.5-9b/glm-4.7-flash, T3: gemma-4-26b-a4b/gemma-4-12b

---

## Quality Metrics

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 520 | 556 |
| Mock count | 47 | 0 |
| Test files | 55 | 62 |
| Services | 34 | 38+ |
| Memory tables | 10 | 14 |
| Lint errors | 53 | 0 |
| Vulnerabilities | 9 | 4 (remaining: diskcache, ragas — no patches available) |

---

## Research Alignment

DEEP's architecture is informed by 6 open-source research foundations:

| Project | License | What Was Adopted |
|---------|---------|------------------|
| DeepTutor (HKUDS) | Apache 2.0 | 4-agent guided learning pipeline |
| PageIndex (VectifyAI) | MIT | Hierarchical document indexing |
| RecursiveMAS | Apache 2.0 | 4 multi-agent collaboration patterns |
| ARA (AmberLJC) | MIT | 4-layer knowledge structure |
| AI-Research-SKILLs | MIT | Modular research pipeline design |
| TurboQuant (Google) | CC-BY-4.0 | 3-4 bit KV cache quantization |

Full attribution: [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)

---

## Architecture Documentation

- **ARCHITECTURE.md** — Complete rewrite with accurate codebase mapping
  - System overview with all 38+ services
  - Middleware stack (6 layers)
  - Memory system (14 tables)
  - Agent routing (complexity scoring, 4 patterns, 5 retrieval modes)
  - Data flows (query + document processing)
  - Security model (7 controls)
  - Performance model
  - Failure modes
  - Infrastructure (Docker, CI/CD, blue-green)

- **README.md** — Architecture section updated with corrected Mermaid diagrams

---

## Breaking Changes

- **LM Studio API endpoints**: v0 endpoints removed, v1 only
- **WebSocket auth**: Token sent as first JSON message, not URL query param
- **`enable_thinking`**: Now defaults to `None` (resolves from settings), not `False`

---

## Dependencies

### Updated
| Package | Old | New | Reason |
|---------|-----|-----|--------|
| lxml | 5.4.0 | 6.1.0 | CVE-2026-41066 (High XXE) |
| pytest | 8.4.2 | 9.0.3 | Dependabot PR #1 (merged) |

### Accepted Risks (no patches available)
| Package | CVE | Severity | Mitigation |
|---------|-----|----------|------------|
| diskcache | CVE-2025-69872 | Moderate | Local-only cache, not network-exposed |
| ragas | CVE-2026-6587 | Low | Multimodal module only, not used by DEEP |

---

## Docker

```bash
# Development
docker compose up -d

# Production (hardened)
docker compose -f docker-compose.prod.yml up -d

# Blue-green (zero-downtime)
./scripts/orchestrate.py deploy
```

---

## Upgrade from v1.1.2

```bash
git pull origin master
cd backend
pip install -r requirements.txt  # lxml 6.1.0
cd ../frontend
npm install
```

No database migrations required. The `staged_observations`, `dead_ends`, `user_l3`, and `provenance_log` tables are created automatically on first startup.

---

## Full Commit Log (v1.1.2 → v1.2.0)

```
d3cae77 docs: fix typo in ACKNOWLEDGEMENTS.md
e347c9f Merge pull request #1 from shinshekai/dependabot/pip/backend/pytest-9.0.3
6740d5d docs: rewrite architecture documentation with accurate codebase mapping
1b7172a docs: add research acknowledgements, fix lxml XXE vulnerability, update license compliance
709ca6e docs: update README v1.2.0, add SECURITY.md, fix test naming
fefdd78 feat: complete all remaining audit/quality/research items (25 fixes)
9e8d270 feat: quality fixes — property tests, contract tests, load tests, model tiers, deterministic recall
c135fd0 feat: Phase 7 Research Alignment — A2, A3, A4, A5
dd17ebe style: auto-fix ruff lint errors and format code
e7b1190 fix: Add missing device_id to test_lm_down_fallback test data
6fa69a4 fix: Post-review bug fixes — 5 issues found during recheck
c18a058 fix: Phase 6 DevOps & Security — L2, L4
2a4b7ca fix: Phase 5 Frontend — L9 sparkline gradient ID collision
7acc017 fix: Phase 4 AI & Prompts — H1, H9, M10
85d6cd1 fix: Phase 3 Performance — M5, M6, M7, H7, L5
fca094d fix: Phase 2 Data Integrity — H3, H5, M1-M4
1b083a2 fix: Phase 1 Foundation — 5 CRITICAL issues (C1/C2/C4/C6/C7)
442fb67 chore: Remove docs/ from git tracking (internal reference only)
a0e98f2 docs: Unified Audit, Quality & Execution Master Plan
97e3ecf docs: Excellence Validation audit + research foundations (6 repos)
2040571 fix(devops/security): Phase 6 — DevOps & Security hardening
4ec642d feat(frontend): Phase 5 — Frontend & UX
4fcd79a feat(backend): Phase 4 — AI & Prompts
4e9bcef fix(backend): StackOverflow-verified hardening
6ead608 feat(architecture): connection health + write semaphore + WAL checkpoint
3bf2f57 fix(memory): compact_episodes atomic transaction + recovery
c7c997c feat(memory): FTS5 chunk integration
b88d142 fix(quality): track_usage INSERT OR IGNORE → plain INSERT
cd70b5b fix(quality): audit fixes — 3 CRITICAL + 2 MEDIUM issues resolved
198730c fix(quality): Phase 3 Performance & Scale
63584ea fix(quality): Phase 2 bug fixes
13f60fb fix(quality): Phase 2 Data Integrity
6bfec14 fix(quality): correct Phase 1 issues
c9dc4c8 fix(quality): Phase 1 Foundation
8f374a1 fix(security): resolve postcss CVE via npm overrides
ec176c4 fix: audit verification cleanup
aafbf80 chore(deps-dev): bump pytest from 8.4.2 to 9.0.3
```

---

**Full Changelog:** https://github.com/shinshekai/Deep/compare/v1.1.2...v1.2.0
