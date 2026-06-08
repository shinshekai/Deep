# Research Foundations: DeepTutor (HKUDS)

## Architecture

- **Two-layer plugin model**: ToolRegistry (Level 1, single-shot tools) + CapabilityRegistry (Level 2, multi-stage workflows)
- **ChatOrchestrator** routes UnifiedContext to selected Capability
- **StreamBus** for capability result fan-out with `cost_summary`

## Memory System (3-Layer)

| Layer | Role | Storage |
|-------|------|---------|
| **L1** | Append-only trace per surface per day (lossless) | `trace/<surface>/<YYYY-MM-DD>.jsonl` |
| **L2** | Per-surface curated facts with footnote citations to L1 | `L2/<surface>.md` |
| **L3** | Cross-surface synthesis: profile, recent, scope, preferences | `L3/<recent\|profile\|scope\|preferences>.md` |

### Trace Forest
Each tutoring interaction = multi-resolution, semantically searchable artifact:
- Level 1: session-level input + global summary
- Level 2: intermediate planning units
- Level 3: fine-grained execution records (tool outputs, evidence, validation)

Every node carries dense embedding → ANN retrieval across entire forest.

## RAG / Retrieval

- **Dual-index**: Knowledge Graph (structural relations) + Dense Embedding Index (semantic similarity)
- **Reciprocal Rank Fusion** for combining results
- **Graph traversal + dense search** → dedup + context budget truncation
- **Configurable chunking**, reranker per KB, auto-routing by file type

## Key Design Choices

1. **Validator shares no reasoning chain with generator** — prevents self-confirming errors
2. **Self-notes compression + hierarchical compression** across sub-goals
3. **Closed-loop cycle**: Weaknesses diagnosed → shapes next questions → improves future explanations
4. **Three specialized memory agents** update profile components
5. **Profile construction is tool-mediated analysis**, not single-pass summary

## Evaluation (TutorBench)

- 270 tasks, 90 profiles, 30 KBs, 5 disciplines
- 10 metrics (1-5 scale) across tutoring and practice dimensions
- Ablation: SKG removal → weakens grounding; DPM removal → weakens adaptation

## Relevance to Our Project

| DeepTutor Pattern | Our Implementation | Gap |
|-------------------|-------------------|-----|
| L1 append-only traces | Episodes table (compact_episodes mutates) | VIOLATION |
| L2 curated facts with citations | Facts table (no positional citations) | PARTIAL |
| L3 cross-surface synthesis | user_profiles JSON blob | MISSING |
| Dual-index RAG (KG + dense) | Tree + vector (no KG) | PARTIAL |
| RRF fusion | Implemented in vector_kb.py | CORRECT |
| Self-notes compression | Naive " \| " join | INSUFFICIENT |
| Separated validator/checker | Check agent sees solver context | VIOLATED |
