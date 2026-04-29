# Phase 10: Vector KB Builder + Hybrid RAG Integration ✅ COMPLETE

> **Completed:** 2026-04-26 — All 6 tasks implemented and tested. 85 tests pass.

**Goal:** Implement the complete vector embedding pipeline (FR-1.3) — from text chunking through embedding generation to vector storage — and wire it into the document ingestion flow and hybrid RAG retrieval, enabling all four retrieval modes (tree, hybrid, naive, combined) to return real results.

**Scope:** Backend services + ingestion integration. No frontend changes needed — existing retrieval UI already supports all pipeline modes.

**Why This Is Next:** Vector search is the #1 blocker. Hybrid RAG and naive retrieval currently return empty results. Every downstream feature (Smart Solver context, Deep Research, Question Generator) benefits from richer retrieval. PageIndex tree search is excellent for single-document deep queries, but multi-document breadth queries need vector search.

---

## Current Status

| Component | Status | Details |
|-----------|--------|---------|
| `services/vector_kb.py` | 🟨 Stub | Interface ready, keyword search works, vector ops return `[]` |
| `services/hybrid_rag.py` | 🟨 Stub | Returns empty — TODO comments mark where vector search goes |
| `routers/knowledge.py` | ✅ Working | Ingestion triggers PageIndex tree only — no embedding pipeline |
| `services/lm_studio_client.py` | ✅ Working | Has `/v1/chat/completions` but NO `/v1/embeddings` method |
| `config.py` | ✅ Has fields | `embedding_host`, `embedding_model`, `embedding_api_key` defined but unused |
| Vector data directory | Empty | `data/knowledge_bases/{kb}/vectors/` created but never populated |

## Working Services (Dependencies)

| Service | Notes |
|---------|-------|
| LMStudioClient | Needs new `embed()` method for `/v1/embeddings` endpoint |
| PageIndexTreeGenerator | Already runs during ingestion — vector pipeline runs parallel |
| DocumentProcessor / TextExtractor | Already extracts raw text from PDF/TXT/MD |
| VectorKBService | Has keyword search + RRF merge logic — needs vector search wired in |
| QueryRouter | Already routes to tree/hybrid/naive/combined — hybrid+naive just return empty |

---

### Task 1: Embedding Service

**Goal:** Add `/v1/embeddings` support to the LM Studio client + create a dedicated embedding service for batch processing.

**Files:**
- Modify: `backend/app/services/lm_studio_client.py` (add `embed()` method)
- Create: `backend/app/services/embedding_service.py` (~120 lines)
- Create: `backend/tests/test_embedding_service.py`

**Steps:**

- [x] **Step 1: Add `embed()` method to LMStudioClient**

Add to `lm_studio_client.py`:

```python
async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
    """Call LM Studio /v1/embeddings endpoint. Returns list of embedding vectors."""
    settings = get_settings()
    base = settings.embedding_host or self.base_url
    api_key = settings.embedding_api_key or self.api_key
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    body = {"input": texts, "model": model or settings.embedding_model or ""}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{base}/v1/embeddings", json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
```

- [x] **Step 2: Create EmbeddingService**

`backend/app/services/embedding_service.py`:

- `EmbeddingService(lm_client)` class
- `async embed_texts(texts: list[str], batch_size=32) -> list[list[float]]` — batches texts and calls `lm_client.embed()`
- `async embed_chunks(chunks: list[dict]) -> list[dict]` — takes chunk dicts `{text, metadata}`, adds `embedding` field
- Handles LM Studio unavailability gracefully (returns empty, logs warning)
- Configurable model via `EMBEDDING_MODEL` env var

- [x] **Step 3: Write tests**

`backend/tests/test_embedding_service.py`:
- Mock LM Studio embed endpoint
- Test batch splitting (33 texts with batch_size=32 → 2 calls)
- Test error handling (LM Studio down → empty results, no crash)
- Test embed_chunks preserves metadata

- [x] **Step 4: Commit**

```bash
git add backend/app/services/lm_studio_client.py backend/app/services/embedding_service.py backend/tests/test_embedding_service.py
git commit -m "feat: add embedding service with LM Studio /v1/embeddings support"
```

---

### Task 2: Text Chunker Service

**Goal:** Split extracted document text into overlapping chunks with metadata, ready for embedding.

**Files:**
- Create: `backend/app/services/text_chunker.py` (~150 lines)
- Create: `backend/tests/test_text_chunker.py`

**Steps:**

- [x] **Step 1: Create TextChunker**

`backend/app/services/text_chunker.py`:

```python
@dataclass
class TextChunk:
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    page_start: int | None = None
    page_end: int | None = None
    doc_id: str = ""
    kb_name: str = ""

class TextChunker:
    def __init__(self, chunk_size=512, chunk_overlap=64, min_chunk_size=50):
        ...
    
    def chunk_text(self, text: str, doc_id: str = "", kb_name: str = "") -> list[TextChunk]:
        """Recursive character chunking with overlap."""
        ...
    
    def chunk_with_pages(self, pages: list[dict], doc_id: str = "", kb_name: str = "") -> list[TextChunk]:
        """Chunk text while preserving page boundary metadata.
        pages: list of {page_num: int, text: str}"""
        ...
```

Chunking algorithm:
1. Split on paragraph boundaries (`\n\n`) first
2. If a paragraph exceeds `chunk_size`, split on sentence boundaries (`. `)
3. If a sentence exceeds `chunk_size`, split on word boundaries
4. Merge small consecutive chunks that together fit within `chunk_size`
5. Add `chunk_overlap` characters of overlap from the previous chunk
6. Track `start_char`/`end_char` positions for citation mapping

- [x] **Step 2: Write tests**

`backend/tests/test_text_chunker.py`:
- Test basic chunking (1000 chars, 512 chunk_size → 2-3 chunks)
- Test overlap (last N chars of chunk[i] == first N chars of chunk[i+1])
- Test page metadata preservation
- Test min_chunk_size filtering (tiny chunks merged)
- Test edge cases: empty text, single-word text, text exactly chunk_size

- [x] **Step 3: Commit**

```bash
git add backend/app/services/text_chunker.py backend/tests/test_text_chunker.py
git commit -m "feat: add text chunker with recursive splitting and page metadata"
```

---

### Task 3: Vector Store Service

**Goal:** Implement local file-based vector storage with cosine similarity search, stored at `data/knowledge_bases/{kb}/vectors/`.

**Files:**
- Modify: `backend/app/services/vector_kb.py` (replace stubs with real implementation)
- Create: `backend/tests/test_vector_store.py`

**Steps:**

- [x] **Step 1: Define storage format**

Each document's vectors stored as two files:
```
data/knowledge_bases/{kb}/vectors/{doc_id}_embeddings.npy   # numpy array (N × dim)
data/knowledge_bases/{kb}/vectors/{doc_id}_metadata.json    # chunk metadata list
```

Metadata JSON:
```json
[
  {
    "chunk_index": 0,
    "text": "The prescribed fee for...",
    "start_char": 0,
    "end_char": 512,
    "page_start": 1,
    "page_end": 1,
    "doc_id": "irpa_fees.pdf"
  }
]
```

- [x] **Step 2: Implement vector storage methods in VectorKBService**

Add to `vector_kb.py`:

```python
async def store_vectors(self, kb_name: str, doc_id: str, 
                        embeddings: np.ndarray, chunks: list[dict]) -> int:
    """Store embedding vectors + metadata. Returns count stored."""

async def delete_vectors(self, kb_name: str, doc_id: str) -> bool:
    """Remove vector data for a document."""

def _load_vectors(self, kb_name: str) -> tuple[np.ndarray | None, list[dict]]:
    """Load all vectors + metadata for a KB (all docs). Cached."""
```

- [x] **Step 3: Implement real `naive_search`**

Replace the stub in `vector_kb.py`:
1. Call `lm_client.embed([query])` to get query vector
2. Load all vectors for the KB via `_load_vectors()`
3. Compute cosine similarity: `scores = embeddings @ query_vec / (norms * query_norm)`
4. Return top_k results above min_score, with chunk metadata as citations

- [x] **Step 4: Wire `hybrid_search` to use real vectors**

Update `hybrid_search()`:
1. `naive_search()` now returns real vector results
2. Keyword search already works via `_keyword_search()`
3. RRF merge already implemented in `_rrf_merge()`
4. Result: hybrid search returns merged ranked results

- [x] **Step 5: Update HybridRAGSearch in hybrid_rag.py**

Wire `HybridRAGSearch.search()` and `naive_search()` to delegate to the real `VectorKBService` methods instead of checking directory emptiness. Pass `lm_client` through for query embedding.

- [x] **Step 6: Add numpy dependency**

```bash
cd backend && pip install numpy
```

Add to `pyproject.toml` under dependencies.

- [x] **Step 7: Write tests**

`backend/tests/test_vector_store.py`:
- Test store_vectors creates npy + json files
- Test _load_vectors reads them back
- Test naive_search with mock embeddings (create synthetic vectors, verify cosine ranking)
- Test hybrid_search combines vector + keyword results
- Test delete_vectors removes files
- Test search on empty KB returns []

- [x] **Step 8: Commit**

```bash
git add backend/app/services/vector_kb.py backend/app/services/hybrid_rag.py backend/tests/test_vector_store.py backend/pyproject.toml
git commit -m "feat: implement vector store with cosine similarity search + wire hybrid RAG"
```

---

### Task 4: Document Ingestion Pipeline Integration

**Goal:** During document upload, run vector embedding generation **in parallel** with PageIndex tree generation. Both pipelines share the same extracted text.

**Files:**
- Modify: `backend/app/routers/knowledge.py` (add embedding pipeline to `_process_document`)
- Modify: `backend/app/main.py` (instantiate new services)

**Steps:**

- [x] **Step 1: Instantiate new services in main.py**

```python
from app.services.embedding_service import EmbeddingService
from app.services.text_chunker import TextChunker

embedding_service = EmbeddingService(lm_client)
text_chunker = TextChunker(chunk_size=512, chunk_overlap=64)
```

- [x] **Step 2: Add parallel embedding pipeline to `_process_document`**

In `knowledge.py`, modify `_process_document()`:

```python
async def _process_document(task_id, file_bytes, doc_id, kb_name, 
                            pageindex_generator, embedding_service, text_chunker, vector_kb):
    # ... existing text extraction ...
    
    _tasks[task_id]["progress"] = 40
    
    # Run BOTH pipelines in parallel
    tree_task = asyncio.create_task(
        pageindex_generator.build_tree(doc_content, model_id, doc_id)
    )
    vector_task = asyncio.create_task(
        _build_vectors(doc_content, doc_id, kb_name, embedding_service, text_chunker, vector_kb)
    )
    
    tree, vector_count = await asyncio.gather(tree_task, vector_task, return_exceptions=True)
    # ... handle results, update progress ...
```

New helper:
```python
async def _build_vectors(doc_content, doc_id, kb_name, embedding_service, text_chunker, vector_kb):
    chunks = text_chunker.chunk_text(doc_content, doc_id, kb_name)
    if not chunks:
        return 0
    chunk_dicts = [{"text": c.text, **asdict(c)} for c in chunks]
    embeddings = await embedding_service.embed_texts([c.text for c in chunks])
    if not embeddings:
        return 0
    import numpy as np
    emb_array = np.array(embeddings, dtype=np.float32)
    count = await vector_kb.store_vectors(kb_name, doc_id, emb_array, chunk_dicts)
    return count
```

- [x] **Step 3: Pass new services through upload route**

Update `upload_document()` to import and pass `embedding_service`, `text_chunker`, and `vector_kb_service` from `app.main`.

- [x] **Step 4: Update task progress reporting**

Add vector count to task completion message:
```python
_tasks[task_id]["message"] = (
    f"Generated PageIndex tree ({tree_nodes} sections) "
    f"and vector KB ({vector_count} chunks embedded)"
)
```

- [x] **Step 5: Update document deletion**

In `delete_document()`, also call `vector_kb.delete_vectors(kb_name, doc_id)` to clean up vector data alongside tree JSON.

- [x] **Step 6: Commit**

```bash
git add backend/app/routers/knowledge.py backend/app/main.py
git commit -m "feat: parallel embedding pipeline during document ingestion

- Text chunking (512 tokens, 64 overlap) + LM Studio embedding
- Vectors stored alongside PageIndex trees
- Both pipelines run concurrently via asyncio.gather
- Document deletion cleans up vector data"
```

---

### Task 5: End-to-End Retrieval Verification

**Goal:** Verify all four retrieval modes return real results after vector data exists.

**Files:**
- Modify: `backend/app/routers/retrieval.py` (ensure VectorKBService is passed lm_client)
- Create: `backend/tests/test_e2e_retrieval.py`

**Steps:**

- [x] **Step 1: Verify retrieval router wiring**

Check `retrieval.py` passes `lm_client` to `VectorKBService` and `HybridRAGSearch` so they can embed queries at search time.

- [x] **Step 2: Write integration tests**

`backend/tests/test_e2e_retrieval.py`:
- Create a test KB with synthetic vectors (mock embedding)
- Test `POST /retrieve` with `pipeline=tree` → uses PageIndex
- Test `POST /retrieve` with `pipeline=naive` → uses vector similarity
- Test `POST /retrieve` with `pipeline=hybrid` → uses vector + keyword RRF merge
- Test `POST /retrieve` with `pipeline=combined` → uses tree + vector merged
- Test `POST /query` → retrieves context + generates answer

- [x] **Step 3: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v
```

- [x] **Step 4: Commit**

```bash
git add backend/app/routers/retrieval.py backend/tests/test_e2e_retrieval.py
git commit -m "test: end-to-end retrieval verification across all pipeline modes"
```

---

### Task 6: Update STATUS.md + Final Validation

**Steps:**

- [x] **Step 1: Start backend and smoke test**

```bash
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- [x] **Step 2: Upload a test document**

```bash
curl -X POST http://localhost:8001/api/v1/knowledge/upload \
  -F "file=@test_document.pdf" -F "kb_name=test_kb"
```

Verify task completes with both tree and vector data.

- [x] **Step 3: Test retrieval**

```bash
curl -X POST http://localhost:8001/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "kb_name": "test_kb", "pipeline": "hybrid"}'
```

Verify non-empty results with citations.

- [x] **Step 4: Update STATUS.md**

Mark Phase 10 as COMPLETE, update service matrix, increment test counts.

- [x] **Step 5: Commit**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs: mark Phase 10 (Vector KB + Hybrid RAG) complete"
```

---

### Non-Goals (Deferred to Future Plans)

| Item | Reason | Future Phase |
|------|--------|-------------|
| Smart Solver dual-loop agents (FR-3) | Requires agent framework design; vector search unblocks it | Phase 11 |
| Question Generator (FR-4) | Needs retrieval working first | Phase 12 |
| Guided Learning (FR-5) | Needs retrieval + agent framework | Phase 13 |
| Deep Research (FR-6) | Needs retrieval + agent framework | Phase 14 |
| Docling RAG pipeline | PyMuPDF works; Docling is opt-in alternative | Future |
| Sentence-window chunking | Recursive character chunking is the default; sentence-window is an optimization | Future |
| Vector index optimization (FAISS/Annoy) | Numpy cosine search is sufficient for <100K chunks | Future |
| Embedding dimension auto-detection | Hardcode to text-embedding-qwen3-embedding-8b for now; make configurable later | Future |
| Incremental re-embedding on KB update | Full re-embed on new document add; skip re-embedding existing docs | v2 |
