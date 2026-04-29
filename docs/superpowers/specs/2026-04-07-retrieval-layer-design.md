# Retrieval Layer Design Spec

> **Date:** 2026-04-07
> **Status:** Draft
> **Related PRD:** FR-2 (Retrieval), REQ-RET-01, REQ-RET-02
> **OpenAPI:** `POST /api/v1/retrieve`, `POST /api/v1/query`

## Problem Statement

The Retrieval Layer currently has skeleton implementations:
- Tree search uses keyword matching instead of LLM reasoning (violates REQ-RET-01)
- Hybrid/Naive RAG return empty results (no Vector KB)
- Query router uses only query-length heuristics
- Combined mode exists but merges suboptimal data

## Requirements

| ID | Requirement | Notes |
|----|-------------|-------|
| REQ-RET-01 | LLM reasons over PageIndex tree summaries (omit raw text) | Must prompt LLM with tree structure only, not raw content |
| REQ-RET-02 | Extract node_ids → map to page ranges → fetch raw text | Enables precise citations with actual document content |
| FR-2.1 | Tree search returns page-level citations | node_id, page_start, page_end per result |
| FR-2.2 | Hybrid RAG for multi-doc queries | Vector + keyword merged |
| FR-2.3 | Pipeline selectable per query | tree/hybrid/naive/combined |
| FR-2.4 | Agents can specify retrieval mode | Used by Smart Solver, Deep Research |
| FR-2.5 | All results produce traceable citations | doc_id, page, section, node_id |
| Perf | Tree search < 5s per retrieval (NFR-1.4) | Performance target |

## Architecture

```
                    POST /retrieve | POST /query
                                   │
                                   ▼
                         ┌──────────────┐
                         │ Query Router │  (improved)
                         └──┬─────┬─┬───┘
             (pipeline)     │     │ │
              ┌─────────────┘     │ │
              │                   │ │
              ▼                   ▼ ▼
        ┌──────────┐       ┌───────────┐
        │  Tree    │       │  Vector   │
        │  Search  │       │  KB       │
        │  (LLM)   │       │  Service  │
        └────┬─────┘       └───┬───┬───┘
             │                  │   │
             │           ┌──────┘   └──────┐
             ▼           ▼                  ▼
        ┌──────────┐ ┌──────────┐    ┌───────────┐
        │ Raw Text │ │ Hybrid    │    │ Naive     │
        │ Extract  │ │ (vec+kw)  │    │ (vec only)│
        └──────────┘ └─────┬─────┘    └───────────┘
               │           │
               ▼           ▼
        ┌──────────┐ ┌───────────┐
        │ Combined  │ │ Merged    │
        │ Mode      │ │ Results   │
        └─────┬─────┘ └─────┬─────┘
              └───────┬─────┘
                      │
                      ▼
              POST /retrieve response
```

## Component Design

### 1. LLM Tree Search (`services/tree_search.py`) — NEW

**Replaces:** `_tree_search()` and `_score_tree_nodes()` in `routers/retrieval.py`

**Three-step process:**
1. **Tree scoring** — Send query + flat node list (title + summary + node_id + page range per node) to T1 model (if < 50 nodes) or T2 (> 50). LLM returns ranked node_ids with relevance scores 0-1.
2. **Text extraction** — Map scored node_ids to page ranges → open source PDF with PyMuPDF → extract raw text for matched pages.
3. **Result enrichment** — Attach full document text to each scored node.

**Prompt:** `TREE_SCORE_PROMPT` — asks LLM to reason over hierarchical summaries and return JSON array: `{"results": [{"node_id": "...", "score": 0.92, "reason": "..."}]}`

**Fallback:** If LLM unavailable or response unparseable → degrade to current keyword matching.

### 2. Raw Text Extraction (`services/text_extractor.py`) — NEW

**Purpose:** Map node_ids to page ranges and extract raw text from PDF files.

**Interface:**
```python
class TextExtractor:
    """Extract raw text from PDF based on page ranges."""
    def __init__(self, kb_base: Path)
    def extract_for_node(self, kb_name: str, tree: dict, node_id: str) -> str | None
    def extract_for_pages(self, pdf_path: Path, page_start: int, page_end: int) -> str | None
```

Uses PyMuPDF (fitz) for PDF text extraction. Skips problematic pages gracefully.

### 3. VectorKB Service (`services/vector_kb.py`) — NEW

**Purpose:** Read and search vector KB files from disk (when FR-1.3 creates them).

**Storage format (anticipated):** `data/knowledge_bases/{kb}/vectors/{chunk_id}.json` with embedding + metadata.

**Interface:**
```python
class VectorKBService:
    def __init__(self, kb_base: Path)
    async def search(self, query: str, kb_name: str, top_k: int) -> list[dict]
    async def hybrid_search(self, query: str, kb_name: str, top_k: int, min_score: float) -> list[dict]
    async def naive_search(self, query: str, kb_name: str, top_k: int, min_score: float) -> list[dict]
    async def keyword_search(self, query: str, kb_name: str, top_k: int) -> list[dict]
```

**For now:** Returns `[]` with info log since no vector data exists. Interface ready for FR-1.3.

**RRF Merge** (for hybrid):
```python
rrf_score = 1 / (60 + rank_vector) + 1 / (60 + rank_keyword)
```

### 4. Query Router (`services/query_router.py`) — IMPROVE EXISTING

**Current:** Length-based heuristics only.

**Improved:**
- Explicit pipeline → use it (already works)
- doc_id → tree search (already works)
- No trees exist → naive with warning
- No vector data → tree with warning
- Complexity 0.3-0.6 + multi-doc → combined
- Complexity > 0.6 → tree (precision)
- Complexity < 0.3 + short query → naive
- Default: tree

### 5. Retrieval Routes (`routers/retrieval.py`) — REWRITE

**Changes:**
- Import and use `TreeSearch` service instead of inline `_tree_search`/`_score_tree_nodes`
- Import `VectorKBService` for hybrid/naive
- `POST /retrieve` delegates to proper services
- `POST /query` enhanced with full tree search + text extraction
- Combined mode runs tree + vector in parallel, merges with weighted scores

### Quantization Scope

This spec covers the **retrieval layer only** (PageIndex reasoning over document structure). It is independent of:

- **Model weight quantization** (GGUF Q4_K_M, Q5_K_M, etc.) — controls model size/quality on disk. Handled by LM Studio.
- **KV cache quantization** (llama.cpp q4_0, q8_0) — compresses key-value pairs during inference. Handled by llama.cpp engine.
- **TurboQuant** (PolarQuant + QJL) — research-grade KV cache compression. Not yet production-grade for llama.cpp.

The retrieval logic is identical regardless of which quantization scheme the underlying model uses. Model tier selection (T1/T2/T3) affects **which model** handles the reasoning request, not **how** tree search or text extraction works.

### 7. Knowledge Routes (`routers/knowledge.py`) — ADD DELETE

**Changes:**
- Add `DELETE /knowledge/bases/{kb_name}/documents/{doc_id}`:
  - Remove tree JSON, raw upload file
  - Update KB registry
  - Return 204 on success

## Error Matrix

| Error | Behavior |
|-------|----------|
| LLM unavailable | Fall back to keyword matching, log warning |
| No trees in KB | Return empty results |
| No vector data | Return empty for vector-based pipelines |
| Invalid PDF | Skip page, continue with others |
| Combined with no data | Return whichever source has data |
| All sources empty | Return `{"results": [], "message": "No matching content"}` |

## Non-Goals (Deferred)

| Item | Reason |
|------|--------|
| Vector KB Builder (FR-1.3) | Separate plan — embedding pipeline, chunking, storage |
| Re-ranking with cross-encoder | Not justified yet for T2 model cost |
| Full Smart Solver integration | Separate plan for dual-loop agents |
| OpenTelemetry instrumentation | Phase 9, observability after functionality |
