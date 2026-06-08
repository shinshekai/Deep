# Deep — Deferred Items Inventory

> Complete catalog of all items deferred across v1.0.3 → v1.1.2 releases.
> Updated: 2026-06-08 (post v1.1.2 + SEC-5-002 resolution)

---

## Status Summary

| Category | Total | Fixed | Deferred | Blocked |
|---|---|---|---|---|
| P0 Defects | 8 | 7 | 1 (audited) | 0 |
| P1 Defects | 17 | 16 | 1 (now resolved) | 0 |
| P2 Items | 58 | 0 | 58 | 0 |
| P3 Items | 12 | 0 | 12 | 0 |
| **TOTAL** | **95** | **23** | **72** | **0** |

---

## 1. DEFERRED P0 Items (1)

### PERF-6-002 — Stale 0.3s `asyncio.sleep` stub
- **File:** `backend/app/services/solve_orchestrator.py:148`
- **Status:** DEFERRED — audit miscounted sleeps (3 claimed, only 1 found + 1 recommend-removal + 3 justified)
- **Effort:** XS (5 min) — but requires domain analysis to confirm stub isn't load-shedding
- **Decision:** Defer to v1.2.0 when solve pipeline is profiled end-to-end

---

## 2. DEFERRED P1 Items (0 — all resolved)

All 17 P1s are now fixed. SEC-5-002 (postcss CVE) was resolved via npm `overrides` in `package.json` (commit `8f374a1`).

---

## 3. DEFERRED P2 Items (58)

### 3.1 AI Engineering (Agent_08)

| ID | Title | Effort | Priority |
|---|---|---|---|
| AI-8-002 | `enable_thinking=True` hardcoded on every LLM call — unnecessary cost + latency | XS (30 min) | MEDIUM |
| AI-8-003 | Ad-hoc inline prompts without versioning or injection hardening | L (1 week) | MEDIUM |
| AI-8-004 | Keyword-based RAG evaluator cannot detect LLM-generated hallucinations | L (1 week) | MEDIUM |
| AI-8-005 | Per-prompt token budgets + caching | M (3 days) | MEDIUM |

### 3.2 Backend Services (Agent_02)

| ID | Title | Effort | Priority |
|---|---|---|---|
| BACK-2-002 | Define explicit `Service` protocol; document the contract | S (1 day) | MEDIUM |

### 3.3 Database & Data (Agent_04)

| ID | Title | Effort | Priority |
|---|---|---|---|
| DB-4-005 | JSON-in-TEXT columns not queryable | M (2 days) | MEDIUM |
| DB-4-006 | `detect_contradictions` loads 200 rows × every insertion (quadratic) | M (2 days) | MEDIUM |
| DB-4-007 | `memory_usage` append-only time series with no retention | S (1 day) | MEDIUM |
| DB-4-008 | `_load_all_vectors` materializes entire KB into single NumPy array | M (2 days) | MEDIUM |
| DB-4-009 | `text_chunker._to_text_chunks` is O(n²) on document size | M (2 days) | MEDIUM |
| DB-4-010 | `fact_relationships` table declared but never used | XS (30 min) | MEDIUM |
| DB-4-011 | `project_profiles.document_count` and `total_pages` denormalized and drift | S (1 day) | MEDIUM |
| DB-4-012 | `user_profiles.profile_json` is opaque JSON | S (1 day) | MEDIUM |
| DB-4-013 | No `CREATE TABLE IF NOT EXISTS` for FTS with explicit tokenizer | S (1 day) | MEDIUM |
| DB-4-014 | KB backup has no compression, no checksum | S (1 day) | MEDIUM |
| DB-4-015 | Session cleanup is filesystem-only; doesn't touch SQLite | S (1 day) | MEDIUM |
| DB-4-016 | No `ON DELETE CASCADE` for `fact_relationships` and other FKs | S (1 day) | MEDIUM |
| DB-4-017 | `recall_episodes` ORDER BY rank is non-deterministic on ties | XS (30 min) | MEDIUM |
| DB-4-018 | `pageindex_generator._regex_heading_fallback` is brittle | S (1 day) | MEDIUM |

### 3.4 Frontend (Agent_03)

| ID | Title | Effort | Priority |
|---|---|---|---|
| FE-3-004 | `system/page.tsx` 40k chars; `global-resource-monitor` re-renders 2s unthrottled | M (2 days) | MEDIUM |
| FE-3-006 | Add Storybook for existing components | M (3 days) | MEDIUM |
| FE-3-007 | `app/page.tsx` uses `router.replace("/chat")` JS redirect — use `next.config.ts` redirects | XS (30 min) | MEDIUM |
| FE-3-008 | No virtualized list in `MessageList` — 200+ messages will jank | S (1 day) | MEDIUM |

### 3.5 DevOps (Agent_07)

| ID | Title | Effort | Priority |
|---|---|---|---|
| DEVOPS-7-004 | No IaC (Terraform/Pulumi) + no DR runbook | L (2 weeks) | MEDIUM |
| DEVOPS-7-005 | CSP `unsafe-eval` and `unsafe-inline` in `next.config.ts:14` | S (1 day) | MEDIUM |
| DEVOPS-7-006 | No `--pull` in CI docker build | XS (30 min) | MEDIUM |
| DEVOPS-7-007 | `.dockerignore` for backend includes `tests/` — pulled in CI | XS (30 min) | MEDIUM |
| DEVOPS-7-008 | Auto-generated token not propagated across replicas | M (2 days) | MEDIUM |
| DEVOPS-7-009 | No `cgroup` v2 resource accounting / no PIDs limit | S (1 day) | MEDIUM |
| DEVOPS-7-010 | `deploy-blue-green.sh` doesn't validate inactive color's image is built | S (1 day) | MEDIUM |
| DEVOPS-7-011 | Production compose mounts host data — `127.0.0.1` ports | S (1 day) | MEDIUM |
| DEVOPS-7-012 | `main.py:13-19` — duplicate `set_tracer_provider` | XS (30 min) | MEDIUM |

### 3.6 Security (Agent_05)

| ID | Title | Effort | Priority |
|---|---|---|---|
| SEC-5-004 | `audit()` emits at `INFO` — security events can be filtered out by handlers that gate on `WARNING+` | XS (15 min) | MEDIUM |
| SEC-5-005 | `_TOKEN_FILE` on Windows has no ACL — `os.chmod` is POSIX-only | S (1 day) | MEDIUM |
| SEC-5-006 | No auth-failure rate limit / lockout — only global 100/min cap | S (1 day) | MEDIUM |
| SEC-5-007 | `is_keyring_available()` cached forever — `lru_cache(maxsize=1)` returns False for process lifetime | XS (15 min) | MEDIUM |
| SEC-5-008 | Frontend `WS_AUTH_TOKEN` is build-time public | S (1 day) | MEDIUM |

### 3.7 Performance (Agent_06)

| ID | Title | Effort | Priority |
|---|---|---|---|
| PERF-6-004 | Memory DB lock contention — single aiosqlite connection pool | M (2 days) | MEDIUM |
| PERF-6-005 | No query plan analysis or index usage monitoring | M (2 days) | MEDIUM |
| PERF-6-006 | No connection pool tuning / monitoring | S (1 day) | MEDIUM |

### 3.8 Quality (Agent_09)

| ID | Title | Effort | Priority |
|---|---|---|---|
| QUAL-9-004 | No property-based testing for data transformations | M (2 days) | MEDIUM |
| QUAL-9-005 | No contract testing between frontend/backend | M (2 days) | MEDIUM |
| QUAL-9-006 | No load testing / performance regression tests | M (2 days) | MEDIUM |

---

## 4. DEFERRED P3 Items (12)

| ID | Title | Effort | Priority |
|---|---|---|---|
| P3-1 | No OpenAPI spec generation / API documentation | S (1 day) | LOW |
| P3-2 | No dependency injection for database connections | M (2 days) | LOW |
| P3-3 | No health check for database connection pool | S (1 day) | LOW |
| P3-4 | No structured logging (JSON format) | S (1 day) | LOW |
| P3-5 | No request ID propagation across services | S (1 day) | LOW |
| P3-6 | No API versioning strategy | M (2 days) | LOW |
| P3-7 | No rate limiting per-user / per-endpoint | M (2 days) | LOW |
| P3-8 | No request/response validation logging | S (1 day) | LOW |
| P3-9 | No distributed tracing across async boundaries | M (2 days) | LOW |
| P3-10 | No graceful shutdown for background tasks | S (1 day) | LOW |
| P3-11 | No API response compression | S (1 day) | LOW |
| P3-12 | No endpoint-level metrics (request count, latency, errors) | M (2 days) | LOW |

---

## 5. Release Roadmap for Deferred Items

### v1.2.0 "Enterprise-Ready" (next release)
1. **PERF-6-002** — Stale 0.3s sleep stub (XS)
2. **DEVOPS-7-004** — IaC + DR runbook (L, 2 weeks)
3. **AI-8-002** — Remove `enable_thinking=True` default (XS)
4. **AI-8-003** — Prompt registry with versioning (L, 1 week)
5. **AI-8-004** — LLM-judge RAG evaluator (L, 1 week)
6. **FE-3-004** — Split system/page.tsx + throttle (M, 2 days)
7. **SEC-5-004** — Audit log level fix (XS)
8. **SEC-5-007** — Keyring cache fix (XS)
9. **DB-4-017** — Deterministic recall ordering (XS)

### v2.0.0 "Production-Grade"
1. **DB-4-005 through DB-4-018** — Database hardening (14 items, ~2 weeks)
2. **BACK-2-002** — Service protocol (S)
3. **FE-3-006** — Storybook (M)
4. **FE-3-007** — Server-side redirect (XS)
5. **FE-3-008** — Message list virtualization (S)
6. **DEVOPS-7-005 through DEVOPS-7-012** — DevOps hardening (8 items, ~1 week)
7. **SEC-5-005 through SEC-5-008** — Security hardening (4 items, ~3 days)
8. **PERF-6-004 through PERF-6-006** — Performance hardening (3 items, ~1 week)
9. **QUAL-9-004 through QUAL-9-006** — Testing hardening (3 items, ~1 week)

### v3.0.0 "Innovation"
1. **INNOV-12-001** — Reasoning DAG (immutable/queryable/composable reasoning artifact)
2. **P3-1 through P3-12** — Infrastructure improvements (12 items, ~2 weeks)
3. **AI-8-005** — Per-prompt token budgets + caching (M)

---

## 6. Effort Summary

| Effort | Count | Total Days |
|---|---|---|
| XS (< 1 day) | 18 | ~4 days |
| S (1 day) | 26 | ~26 days |
| M (2-3 days) | 22 | ~55 days |
| L (1-2 weeks) | 6 | ~30 days |
| **TOTAL** | **72** | **~115 days** |

> **Note:** Not all items need to be implemented. Prioritize based on:
> 1. Security impact (SEC-5-004 through SEC-5-008)
> 2. Reliability impact (DB-4-005 through DB-4-018)
> 3. Developer experience (AI-8-002 through AI-8-005, FE-3-006)
> 4. Operational maturity (DEVOPS-7-004 through DEVOPS-7-012)
