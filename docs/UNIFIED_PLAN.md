# Deep — Unified Audit, Quality & Execution Master Plan

> Single source of truth combining all audit findings, quality items, and execution plans.
> Merged from: EXCELLENCE_AUDIT.md, AUDIT_MASTER_SYNTHESIS.md, QUALITY_EXECUTION_PLAN.md, DEFERRED_ITEMS.md
>
> Last updated: 2026-06-08 (post v1.1.2)

---

## How to Read This Document

| Section | Purpose |
|---|---|
| **1. Current Status** | What's done, what's pending, what's blocked |
| **2. Active Issues** | Every open item, deduplicated and ranked |
| **3. Research Gaps** | Misalignment with research foundations |
| **4. Architecture Gaps** | Structural issues requiring design decisions |
| **5. Release Roadmap** | What ships when |
| **6. Execution Plan** | Domain-by-domain implementation guide |

---

## 1. Current Status

### Release History

| Release | Key Deliverables |
|---|---|
| v1.0.0 -> v1.0.3 | Auth tokens, WAL mode, FTS5, backups, security hardening |
| v1.1.0 -> v1.1.2 | 60 P0/P1/P2/P3 fixes, all P0s + P1s closed |
| Supermemory Phases 1-4 | Memory architecture, episodic/factual storage (47 tasks) |
| Quality Execution Phases 1-6 | FTS5 porter, compaction, architecture hardening (30+ commits) |

### Score Matrix (10-agent audit)

| Dimension | Score | Verdict |
|---|---|---|
| Systems Architecture | 78/100 | Strong; Service-Locator coupling |
| Backend Engineering | 60/100 | Feature-complete; loose seams |
| Frontend Engineering | 62/100 | Velocity outran discipline |
| Database & Data | 64/100 | Conditional Pass; missing indexes |
| Security | 70/100 | Conditional Go (Local-First only) |
| Performance | 58/100 | 4 critical hot-path liabilities |
| DevOps | 64/100 | OTel broken, no IaC |
| AI Engineering | 71/100 | Production-grade local-first |
| Code Quality | 66/100 | Indie-team scaling pains |
| Innovation | 71/100 | Ferrari engine on Model-T dashboard |
| **Composite** | **66.4/100** | **Local-First Production-Ready** |

### Summary Counts

| Category | Fixed | Open | Total |
|---|---|---|---|
| CRITICAL | 0 | 7 | 7 |
| HIGH | 3 | 14 | 17 |
| MEDIUM | 7 | 3 | 10 |
| LOW | 2 | 9 | 11 |
| ARCHITECTURE | 0 | 6 | 6 |
| DEFERRED P2 | 0 | 58 | 58 |
| DEFERRED P3 | 0 | 12 | 12 |
| **TOTAL** | **12** | **109** | **121** |

---

## 2. Active Issues — Deduplicated & Ranked

### 2.1 CRITICAL Issues (Must Fix Before Next Release)

| ID | Title | File | Why It Matters |
|---|---|---|---|
| **C1** | batch_resolve_contradictions breaks transaction integrity | memory_service.py:724 | store_episode() commits inside outer transaction. Remaining groups execute outside atomicity. Data loss risk on partial failure. |
| **C2** | outcome_rating hardcoded to 0.0, never updated | memory_service.py:368, 976 | Every episode compacted after 90 days regardless of quality. Missing feature disguised as working code. |
| **C3** | Contradictions silently lose both facts | memory_service.py:721 | Both sides archived, no user confirmation. ARA requires unresolved decision nodes. ESCALATED. |
| **C4** | Check agent validates its own output | solve_orchestrator.py:311, 333 | Self-confirming loop. DeepTutor explicitly separates validator from generator. |
| **C5** | Auth token in URL query parameter | lib/websocket.ts:196 | Query params logged in server logs, browser history. OWASP violation. ESCALATED. |
| **C6** | Dual scroll containers break virtualization | ChatMessageList.tsx:247, 296 | Two nested scroll containers. Virtualizer tracks wrong element. |
| **C7** | complete handler re-subscribes every chunk | chat/page.tsx:115 | Dependency array includes streamingAnswer/streamingSteps. Causes subscription churn. |

### 2.2 HIGH Issues (Should Fix Before Next Major)

| ID | Title | File | Status |
|---|---|---|---|
| **H1** | LLM-judge uses 0.7 temperature instead of 0.1 | rag_eval.py:160 | OPEN |
| **H2** | Keyword heuristics dont match what they claim | rag_eval.py:63-102 | JUSTIFIED (directional signals only) |
| **H3** | Combined pipeline loses ranking (no RRF) | retrieval_service.py:140-146 | OPEN |
| **H4** | L1 append-only invariant violated | memory_service.py:968, 472 | JUSTIFIED (compaction needed for storage) |
| **H5** | Compaction summary severely lossy | memory_service.py:991 | OPEN |
| **H6** | Platform layout fully client-rendered | (platform)/layout.tsx:1 | JUSTIFIED (uses hooks) |
| **H7** | Duplicated VRAM telemetry | layout.tsx:85 | OPEN |
| **H8** | Token endpoint unauthenticated | ws-ticket/route.ts:5-14 | ESCALATED |
| **H9** | Judge prompt YAML is dead code | rag_eval.py:27-40 | OPEN |

### 2.3 MEDIUM Issues

| ID | Title | Status |
|---|---|---|
| **M1** | is_available ignores client state | OPEN |
| **M2** | Faithfulness fallback inconsistent | OPEN |
| **M3** | Burst latency uses timestamps not durations | OPEN |
| **M4** | Retrieval precision always passes | OPEN |
| **M5** | Complexity routing never activates | OPEN |
| **M6** | Response cache relative path | OPEN |
| **M7** | Response cache singleton not thread-safe | OPEN |
| **M8** | list_episodes duplicates row-to-dict conversion | DEFERRED |
| **M9** | No PRAGMA synchronous=NORMAL | DEFERRED |
| **M10** | No PRAGMA cache_size | DEFERRED |

### 2.4 LOW Issues

| ID | Title | Status |
|---|---|---|
| **L1** | _safe is dead code | OPEN |
| **L2** | _store_chunks SQL injection surface | DEFERRED |
| **L3** | _profile_backoff_state not persisted | DEFERRED |
| **L4** | recall_facts holds BEGIN IMMEDIATE during read+update | DEFERRED |
| **L5** | compact_episodes tracks usage with wrong device_id | OPEN |
| **L6** | prompt_registry.render() does not escape values | DEFERRED |
| **L7** | prompt_registry duplicate names overwrite silently | DEFERRED |
| **L8** | prompt_registry singleton not thread-safe | DEFERRED |
| **L9** | Sparkline gradient ID collision | DEFERRED |
| **L10** | ChatHeader unnecessary client component | DEFERRED |
| **L11** | localStorage writes on every message change | DEFERRED |

---

## 3. Research Gaps — Misalignment with Research Foundations

### 3.1 Research Sources Studied

| Source | Key Pattern | Our Coverage |
|---|---|---|
| DeepTutor (HKUDS) | 3-layer memory, dual-index RAG, separated validator | Partial |
| PageIndex (VectifyAI) | Tree-based agentic retrieval, verification-as-invariant | Partial |
| RecursiveMAS | Latent-space adapter communication | N/A (different layer) |
| Agent-Native Artifacts (ARA) | 4-layer knowledge package, append-only traces | Gap |
| AI Research SKILLs | Two-loop orchestration, progressive disclosure | Partial |
| DeepTutor Claude Skill | Thin tool layer, prompt-as-architecture | Partial |

### 3.2 Research Pattern Coverage

| Research Pattern | DeepTutor Spec | Our Implementation | Gap |
|---|---|---|---|
| L1 append-only traces | Trace per surface per day | Episodes table (compact mutates) | VIOLATED |
| L2 curated facts with citations | Footnote citations to L1 | Facts table (no positional citations) | PARTIAL |
| L3 cross-surface synthesis | Profile, recent, scope, preferences | user_profiles JSON blob | MISSING |
| Dual-index RAG | KG + Dense Embeddings | Tree + Vector (no KG) | PARTIAL |
| Reciprocal Rank Fusion | RRF for combining results | In vector_kb.py only | PARTIAL |
| Self-notes compression | Structured key-value extraction | Naive pipe join | INSUFFICIENT |
| Separated validator | No shared reasoning chain | Check agent sees solver context | VIOLATED |
| Verification-as-invariant | Every generation pass verified | Check runs once at end | MISSING |
| Dead ends as first-class | Typed nodes with failure_mode | Not represented | MISSING |
| Provenance tracking | user/ai-suggested/ai-executed | Not implemented | MISSING |
| Progressive crystallization | Stage observations, crystallize on closure | Immediate storage | MISSING |

### 3.3 What Would Close the Gap

1. **Knowledge Graph integration** — the most impactful missing component from DeepTutor
2. **Verification-as-invariant pipeline** — PageIndex's key insight
3. **Proper contradiction resolution** — with user confirmation (ARA pattern)
4. **Separated check agent reasoning** — from solve agent context
5. **L3 synthesis engine** — cross-surface profile construction

---

## 4. Architecture Gaps — Structural Issues

| ID | Gap | Impact | Effort |
|---|---|---|---|
| **A1** | No Knowledge Graph index | DeepTutor dual-index requires KG + Dense | L (2 weeks) |
| **A2** | No verification-as-invariant | PageIndex requires every generation verified | M (1 week) |
| **A3** | No L3 cross-surface synthesis | DeepTutor L3 synthesizes across surfaces | M (1 week) |
| **A4** | No dead ends as first-class | ARA requires failed approaches as typed nodes | M (3 days) |
| **A5** | No provenance tracking | ARA requires user/ai-suggested/ai-executed tags | M (3 days) |
| **A6** | No progressive crystallization | ARA stages observations before crystallization | L (1 week) |

### From 10-Agent Audit (Architecture & Backend)

| ID | Title | Effort |
|---|---|---|
| ARCH-1-001 | Services import router handlers (architectural inversion) | M (1 day) |
| ARCH-1-002 | Global app.state singleton imported in 26+ files | M (1-2 days) |
| ARCH-1-003 | 16+ fire-and-forget asyncio.create_task calls | M (1 day) |
| BACK-2-001 | 8 background tasks with no persistence on restart | M (2 days) |
| BACK-2-002 | Define explicit Service protocol | S (1 day) |

---

## 5. Release Roadmap

### v1.2.0 "Enterprise-Ready" (Next Release)

**Theme:** Fix the 7 CRITICAL issues + close remaining HIGH items.

| Workstream | Items |
|---|---|
| CRITICAL fixes | C1 (transaction integrity), C2 (outcome_rating), C4 (self-confirming), C6 (virtualization), C7 (subscription churn) |
| HIGH fixes | H1 (judge temp), H3 (RRF), H5 (compaction summary), H7 (VRAM dedup), H9 (prompt registry) |
| MEDIUM fixes | M1-M7 (eval, benchmark, cache fixes) |
| Architecture | ARCH-1-001 (kill router-from-service), ARCH-1-002 (DI Container) |
| Security | C3 (contradiction resolution), C5 (WS auth), H8 (token endpoint) |

### v2.0.0 "Production-Grade"

**Theme:** Database hardening + full research alignment.

| Workstream | Items |
|---|---|
| Database | DB-4-005 through DB-4-018 (14 items, ~2 weeks) |
| Research alignment | A1 (KG), A2 (verification), A3 (L3 synthesis) |
| Frontend | FE-3-004 split, FE-3-006 Storybook, FE-3-008 virtualization |
| DevOps | DEVOPS-7-005 through DEVOPS-7-012 (8 items) |
| Security | SEC-5-005 through SEC-5-008 (4 items) |
| Performance | PERF-6-004 through PERF-6-006 (3 items) |
| Testing | QUAL-9-004 through QUAL-9-006 (property, contract, load) |

### v3.0.0 "Reasoning as First-Class"

**Theme:** From product to platform.

| Workstream | Items |
|---|---|
| Reasoning DAG | Immutable, queryable, composable reasoning artifact |
| Memory Graph UI | Visualize everything the system knows |
| Open-source extraction | 3-5 standalone packages (ara-runtime, recursive-solver, agent-verify) |
| Diff-over-DAG | Reasoning branches, merges, time-travels |
| Infrastructure | DEVOPS-7-004 (Terraform/IaC), DR runbook |

---

## 6. Execution Plan — Domain by Domain

### Phase 1: Foundation (Week 1)

1. C1 — Fix batch_resolve_contradictions transaction integrity (XS)
2. C2 — Add outcome_rating update mechanism (S)
3. C4 — Separate check agent reasoning from solve agent (M)
4. C6 — Remove overflow-y-auto from outer container (XS)
5. C7 — Use ref for complete handler dependencies (XS)

### Phase 2: Data Integrity (Week 1-2)

6. H3 — Apply RRF in combined retrieval pipeline (S)
7. H5 — Richer compaction summary with answer snippets (S)
8. M1 — Fix is_available to check client state (XS)
9. M2 — Fix faithfulness fallback consistency (XS)
10. M3 — Fix burst latency calculation (XS)
11. M4 — Fix retrieval precision metric (XS)

### Phase 3: Performance (Week 2-3)

12. M5 — Fix complexity routing activation (XS)
13. M6 — Fix response cache relative path (XS)
14. M7 — Fix response cache singleton thread safety (XS)
15. H7 — Deduplicate VRAM telemetry (S)
16. L5 — Fix compact_episodes device_id tracking (XS)

### Phase 4: AI & Prompts (Week 3-4)

17. H1 — Fix LLM-judge temperature (XS)
18. H9 — Remove inline prompt, use prompt registry (S)
19. M10 — Add PRAGMA cache_size (XS)

### Phase 5: Frontend (Week 4-5)

20. L10 — Convert ChatHeader to Server Component (XS)
21. L11 — Optimize localStorage writes (S)
22. L9 — Fix sparkline gradient ID collision (XS)

### Phase 6: DevOps & Security (Week 5-6)

23. C5 — WebSocket auth via subprotocol or first-message (M)
24. H8 — Add auth to token endpoint (S)
25. C3 — Contradiction resolution with user confirmation (M)
26. L2 — Parameterize _store_chunks table names (XS)
27. L4 — Reduce recall_facts lock duration (S)

### Phase 7: Research Alignment (Week 6-8)

28. A2 — Verification-as-invariant pipeline (M)
29. A3 — L3 cross-surface synthesis engine (M)
30. A4 — Dead ends as first-class nodes (M)
31. A5 — Provenance tracking (M)

### Phase 8: Testing & Innovation (Week 8-10)

32. QUAL-9-004 — Property-based testing (M)
33. QUAL-9-005 — Contract testing (M)
34. QUAL-9-006 — Load testing (M)
35. A6 — Progressive crystallization (L)
36. A1 — Knowledge Graph integration (L)

---

## Appendix A — Effort Summary

| Effort | Count | Total Days |
|---|---|---|
| XS (< 1 day) | 25 | ~6 days |
| S (1 day) | 18 | ~18 days |
| M (2-3 days) | 20 | ~50 days |
| L (1-2 weeks) | 8 | ~40 days |
| **TOTAL** | **71** | **~114 days** |

---

## Appendix B — Quality Metrics

| Metric | Target |
|---|---|
| Test coverage | >90% for new code |
| Lint errors | 0 new ruff/black/isort errors |
| Type coverage | mypy strict mode passes |
| Security | 0 known vulnerabilities |
| Performance | No regression in existing benchmarks |
| Documentation | ADR for each architectural decision |

---

## Appendix C — Research References

All research summaries saved in docs/research/:
- deeptutor.md — 3-layer memory, dual-index RAG, separated validator
- pageindex.md — Tree-based agentic retrieval, verification-as-invariant
- recursivemas.md — Latent-space adapter communication
- agent-native.md — 4-layer knowledge package, append-only traces
- ai-research-skills.md — Two-loop orchestration, progressive disclosure
- deeptutor-claude-skill.md — Thin tool layer, prompt-as-architecture
- EXCELLENCE_AUDIT.md — Full audit with line-number references
