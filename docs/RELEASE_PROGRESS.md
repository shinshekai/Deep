# Release Progress — Audit Remediation

This file tracks remediation of findings from the full-spectrum excellence
audit. It is updated as fixes land. Each item links to its severity and the
branch/MR that addresses it.

## Legend

- ✅ Done (merged)
- 🟡 In progress (on a branch / open MR)
- ⬜ Not started

## Phase 1 — Quick Wins (low risk, high ROI)

| Status | Severity | Finding | Fix | Branch |
|--------|----------|---------|-----|--------|
| 🟡 | CRITICAL | CI pipeline never runs — branch filters target `main`/`develop` but the default branch is `master`. | Added `master` to push and PR branch filters in `.github/workflows/production-readiness.yml`. | `fix/audit-critical-quick-wins` |
| 🟡 | HIGH | `verify_feedback` could be referenced before assignment in the solve retry path (`solve_orchestrator._run_dual_loop`), a latent `NameError` masked by `# noqa: F821`. | Initialize `verify_feedback = ""` before the solve loop and remove the `noqa`. | `fix/audit-critical-quick-wins` |

## Phase 2 — Production Hardening (larger changes, handled in dedicated MRs)

| Status | Severity | Finding | Planned fix |
|--------|----------|---------|-------------|
| ⬜ | CRITICAL | Shared single `aiosqlite` connection is mutated by concurrent unawaited writes; common write paths bypass `_write_lock`, risking races/corruption under load. | Serialize all writes through `_write_lock` or move to a per-operation connection / small pool. |
| ⬜ | CRITICAL | Prompt injection via unescaped retrieved RAG / memory / dead-end context concatenated into agent prompts. | Fence retrieved content as untrusted data with explicit delimiters and a system directive to treat it as data, not instructions. |
| ⬜ | HIGH | IDOR: memory endpoints trust a caller-supplied `device_id` with no server binding, contradicting the "no cross-device leakage" claim. | Bind `device_id` to the authenticated session/ticket and reject mismatches. |
| ⬜ | HIGH | `secureFetch` only injects the auth header for `localhost:8001`; non-localhost deployments silently 401. | Derive the trusted origin from `API_BASE_URL` instead of a hardcoded host. |

## Phase 3 — Quality & AI Maturity

| Status | Severity | Finding | Planned fix |
|--------|----------|---------|-------------|
| ⬜ | MEDIUM | Agent prompts are hardcoded inline despite an existing `prompt_registry` + `prompts/*.yaml` infrastructure. | Move agent prompts into the registry and version them. |
| ⬜ | MEDIUM | Evaluation assets (`rag_eval.py`, `evaluation_dataset.json`, RAGAS report) exist but are not a CI regression gate. | Add a CI job that fails on eval regression. |
| ⬜ | MEDIUM | README over-claims vs. code (table counts, CSP, WCAG AA, "tested"). | Reconcile docs to the actual schema and shipped behavior. |

## Changelog

- **2026-06-13** — Phase 1 started on branch `fix/audit-critical-quick-wins`:
  enabled CI on `master`, guarded the `verify_feedback` retry-path
  `NameError`. Both changes are surgical and do not alter existing behavior
  on the success path.
