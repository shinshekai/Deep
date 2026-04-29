# Retrieval Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace skeleton retrieval with real LLM-based tree search, a VectorKB service interface, an improved query router, and raw text extraction — completing FR-2 (Retrieval) requirements REQ-RET-01 and REQ-RET-02.

**Architecture:** Services (TreeSearch, TextExtractor, VectorKBService, QueryRouter) are wired through a rewritten retrieval.py route. Query uses TreeSearch (LLM reasoning over pageindex summaries) → TextExtractor (map node_ids to PDF pages) → LLM answer. VectorKB provides stub interfaces for hybrid/naive until FR-1.3 builds the data.

**Tech Stack:** FastAPI, PyMuPDF (fitz), LMStudioClient (T1/T2 inference), asyncio, pytest

> **Quantization Scope:** The retrieval layer uses LLM reasoning and document search — it does NOT implement TurboQuant or model quantization. Those are separate layers:
>
> - **Model weight quantization** (e.g., Qwen3-8B Q5_K_M GGUF) — compresses model weights on disk and at load time. Handled by LM Studio/llama.cpp.
> - **KV cache quantization** (llama.cpp q4_0, q8_0 types via `--cache-type-k`/`--cache-type-v`) — compresses key-value pairs during inference. Handled by llama.cpp.
> - **TurboQuant** — Google's research-grade KV cache compression algorithm (PolarQuant + QJL). Not yet integrated into llama.cpp/production systems.
>
> The retrieval layer only cares about the LLM *behaviour* (reasoning over summaries), not whether the KV cache or model weights are compressed. All model tiers (T1/T2/T3) described in the inference strategy work identically for retrieval purposes.

---

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `services/tree_search.py` | **Create** | LLM scoring of PageIndex tree nodes + fallback to keyword |
| `services/text_extractor.py` | **Create** | Map node_ids to page ranges → extract raw text from PDF |
| `services/vector_kb.py` | **Create** | Vector KB service with RRF hybrid merge (returns empty until FR-1.3) |
| `services/query_router.py` | **Modify** | Add complexity-aware routing + fallback logic |
| `routers/retrieval.py` | **Rewrite** | POST /retrieve and POST /query using new services |
| `main.py` | **Modify** | Wire services into lifespan |
| `config.py` | **Modify** | Add retrieval-specific settings |
| `tests/test_tree_search.py` | **Create** | Tree search unit tests |
| `tests/test_text_extractor.py` | **Create** | Text extraction unit tests |
| `tests/test_vector_kb.py` | **Create** | Vector KB stub tests |
| `tests/test_query_router.py` | **Create** | Router logic tests |
| `tests/test_retrieval.py` | **Create** | Route-level integration tests |

---

### Task 1: TextExtractor Service

**Files:**
- Create: `backend/app/services/text_extractor.py`
- Test: `backend/tests/test_text_extractor.py`

TextExtractor is responsible for raw document text retrieval. It takes a knowledge base name, loads the pageindex tree, resolves which physical document file belongs to the document, and extracts text by page range using PyMuPDF.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_text_extractor.py
"""Text extractor service tests."""

import pytest
import io
from pathlib import Path
from unittest.mock import patch, MagicMock
import fitz  # PyMuPDF

TEST_KB_BASE = Path("data/knowledge_bases")


class FakeDoc:
    """Fake PDF document that returns text for page lookups."""
    def __init__(self, page_texts: dict[int, str]):
        self._page_texts = page_texts
        self.page_count = max(page_texts.keys()) + 1 if page_texts else 0

    def __getitem__(self, idx: int):
        text = self._page_texts.get(idx, "")
        page_mock = MagicMock()
        page_mock.get_text.return_value = text
        return page_mock

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@patch("fitz.open")
def test_extract_for_pages_returns_text(mock_fitz_open):
    """Pages 2-4 text is concatenated correctly."""
    from app.services.text_extractor import TextExtractor

    fake_doc = FakeDoc({
        0: "Title page",
        1: "Introduction text here",
        2: "Chapter one details",
        3: "More chapter content",
        4: "Conclusion",
    })
    mock_fitz_open.return_value = fake_doc

    extractor = TextExtractor(TEST_KB_BASE)
    result = extractor.extract_for_pages(
        "/fake/path.pdf", page_start=1, page_end=3
    )
    assert "Introduction text here" in result
    assert "Chapter one details" in result
    assert "More chapter content" in result
    fake_doc.close()


@patch("fitz.open")
def test_extract_for_pages_handles_missing_file(mock_fitz_open):
    """Returns None when document cannot be opened."""
    from app.services.text_extractor import TextExtractor

    mock_fitz_open.side_effect = FileNotFoundError("not found")
    extractor = TextExtractor(TEST_KB_BASE)
    result = extractor.extract_for_pages("/nonexistent.pdf", 0, 2)
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_text_extractor.py -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.text_extractor'"

- [ ] **Step 3: Write implementation**

```python
"""TextExtractor — maps PageIndex node_ids to raw PDF text.

Implements REQ-RET-02: Extract node_ids → map to page ranges →
extract raw document text from source PDF files.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

UPLOAD_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases" / "uploads"


class TextExtractor:
    """Extract raw text from PDF files based on page ranges."""

    def __init__(self, kb_base: Path):
        self.kb_base = kb_base

    def extract_for_pages(
        self, pdf_path: str, page_start: int = 0, page_end: int = 0
    ) -> Optional[str]:
        """Extract text from a PDF for the given page range (0-indexed).

        Returns concatenated text for pages [page_start, page_end].
        Returns None if file cannot be opened.
        """
        import fitz

        # Handle same-page case
        if page_end == 0:
            page_end = page_start

        try:
            doc = fitz.open(pdf_path)
            pages_to_read = range(page_start, page_end + 1)
            texts = []
            for page_idx in pages_to_read:
                if 0 <= page_idx < doc.page_count:
                    texts.append(doc[page_idx].get_text("text"))
            doc.close()
            return "\n\n".join(texts) if texts else ""
        except Exception as e:
            logger.warning(f"Cannot extract text from {pdf_path}: {e}")
            return None

    def extract_for_node(
        self, kb_name: str, doc_id: str, tree: dict, node: dict
    ) -> Optional[str]:
        """Extract raw text for a specific tree node.

        Finds the source PDF from uploads, maps node page_start/page_end
        to actual document text.
        """
        page_start = node.get("page_start", 0)
        page_end = node.get("page_end", 0)

        # Find source PDF file
        upload_path = UPLOAD_BASE / kb_name / doc_id
        if not upload_path.exists():
            # Try with common extensions
            for ext in [".pdf", ".txt", ".md"]:
                candidate = UPLOAD_BASE / kb_name / (doc_id + ext)
                if candidate.exists():
                    upload_path = candidate
                    break

        if not upload_path.exists():
            logger.warning(f"Source document not found for {kb_name}/{doc_id}")
            return None

        return self.extract_for_pages(str(upload_path), page_start, page_end)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_text_extractor.py -v
```
Expected: PASS (2/2)

- [ ] **Step 5: Add more robustness tests**

```python
@patch("fitz.open")
def test_extract_for_pages_handles_out_of_range(mock_fitz_open):
    """Handles page ranges beyond document length gracefully."""
    from app.services.text_extractor import TextExtractor

    fake_doc = FakeDoc({0: "Only page"})
    mock_fitz_open.return_value = fake_doc

    extractor = TextExtractor(TEST_KB_BASE)
    result = extractor.extract_for_pages(
        "/fake/path.pdf", page_start=0, page_end=10
    )
    assert "Only page" in result
    fake_doc.close()


def test_extract_for_node_returns_none_when_doc_missing():
    """Returns None if source PDF cannot be found."""
    from app.services.text_extractor import TextExtractor

    extractor = TextExtractor(TEST_KB_BASE)
    tree = {"doc_id": "nonexistent"}
    node = {"page_start": 0, "page_end": 2}
    result = extractor.extract_for_node("unknown_kb", "nonexistent", tree, node)
    assert result is None
```

- [ ] **Step 6: Run all tests**

```bash
cd backend && python -m pytest tests/test_text_extractor.py -v
```
Expected: PASS (4/4)

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/services/text_extractor.py tests/test_text_extractor.py
git commit -m "feat: add TextExtractor service for raw document text retrieval

- Maps node_ids to page ranges and extracts text via PyMuPDF
- Handles missing files and out-of-range pages gracefully
- Returns None on extraction errors with warning log"
```

---

### Task 2: TreeSearch Service (LLM-based)

**Files:**
- Create: `backend/app/services/tree_search.py`
- Test: `backend/tests/test_tree_search.py`

This is the core of REQ-RET-01. Instead of keyword matching, an LLM (T1 for small trees, T2 for large) reasons over the PageIndex tree structure and returns scored, ranked node_ids.

Important constraints from the architecture:
- **REQ-RET-01**: "backend must construct a prompt containing the user query and the serialized PageIndex tree structure, specifically omitting the raw document text to force the LLM to reason over the hierarchical summaries"
- Tree must be serialized compactly (title + summary + node_id + page range per node)
- LLM returns JSON array of scored node_ids with relevance scores
- Fallback to keyword matching when LLM unavailable

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_tree_search.py
"""Tree search service tests — LLM reasoning over PageIndex trees."""

import pytest
from unittest.mock import AsyncMock, MagicMock

# Sample PageIndex tree for tests
SAMPLE_TREE = {
    "doc_id": "test_doc",
    "title": "Test Document",
    "total_pages": 10,
    "root": {
        "node_id": "root",
        "title": "Test Document",
        "summary": "A document about machine learning",
        "page_start": 0,
        "page_end": 9,
        "children": [
            {
                "node_id": "node_1_0",
                "title": "Neural Networks",
                "summary": "Overview of neural network architectures and training methods",
                "page_start": 0,
                "page_end": 4,
                "children": [
                    {
                        "node_id": "node_2_0",
                        "title": "Deep Learning",
                        "summary": "Deep learning models including CNNs, RNNs, and transformers",
                        "page_start": 2,
                        "page_end": 4,
                        "children": [],
                    }
                ],
            },
            {
                "node_id": "node_1_1",
                "title": "Training Methods",
                "summary": "Backpropagation, gradient descent, and optimization techniques",
                "page_start": 5,
                "page_end": 7,
                "children": [],
            },
            {
                "node_id": "node_1_2",
                "title": "Evaluation",
                "summary": "Metrics for model evaluation including accuracy and F1 score",
                "page_start": 8,
                "page_end": 9,
                "children": [],
            },
        ],
    },
}


@pytest.fixture
def mock_lm_client():
    client = AsyncMock()

    async def mock_stream_chat(messages, **kwargs):
        user_msg = messages[-1]["content"].lower() if messages else ""
        if "list relevant node_ids" in user_msg:
            return (
                '[{"node_id": "node_1_0", "score": 0.92, "reason": "Covers '
                'neural network architectures and training"}, '
                '{"node_id": "node_1_1", "score": 0.65, "reason": "Training '
                'methods are relevant to building networks"}]'
            )
        return ""

    client.stream_chat = mock_stream_chat
    client.check_health = AsyncMock(return_value=True)
    return client


@pytest.fixture
def tree_search(mock_lm_client):
    from app.services.tree_search import TreeSearch
    return TreeSearch(lm_client=mock_lm_client)


@pytest.mark.asyncio
async def test_tree_search_returns_scored_nodes(tree_search):
    """LLM scoring returns ranked node_ids with scores."""
    results = await tree_search.search(
        query="How to build a neural network?",
        kb_name="test_kb",
        doc_id="test_doc",
        tree=SAMPLE_TREE,
        top_k=3,
        min_score=0.3,
    )
    assert len(results) > 0
    assert results[0]["doc_id"] == "test_doc"
    assert "score" in results[0] or "relevance_score" in results[0]


@pytest.mark.asyncio
async def test_tree_search_respects_doc_id_filter(tree_search):
    """When doc_id is specified, only searches that document's tree."""
    results = await tree_search.search(
        query="training methods",
        kb_name="test_kb",
        doc_id="test_doc",
        tree=SAMPLE_TREE,
        top_k=2,
        min_score=0.3,
    )
    # Should return nodes from the specified document
    assert all(r.get("doc_id") == "test_doc" for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_tree_search.py::test_tree_search_returns_scored_nodes -v
```
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write implementation**

```python
"""TreeSearch — LLM reasoning-based retrieval over PageIndex trees.

Implements REQ-RET-01: Backend constructs a prompt with query + tree
structure (omitting raw text), LLM reasons over hierarchical summaries.

REQ-RET-02: Backend parses LLM response to extract node_ids, maps to
page ranges, extracts raw text from source PDF.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from app.services.text_extractor import TextExtractor

logger = logging.getLogger(__name__)

TREE_SCORE_PROMPT = """You are a document retrieval assistant. You will be given:
1. A user query
2. A page index tree from a document showing the hierarchical structure

Your task is to identify which sections (nodes) of the document tree are most
relevant to the query. Return ONLY a JSON array of relevant nodes. Do not
include markdown code fence markers.

For each relevant node, provide:
- "node_id": the exact node_id
- "score": relevance from 0.0 to 1.0
- "reason": brief explanation (1 sentence)

Return nodes in order of relevance (most relevant first).
Only include nodes with actual relevance (score > 0.1).

## PageIndex Tree
{tree_json}

## Query
{query}

## Response (JSON array only)"""

TREE_SCORE_FEW_SHOT_SYSTEM = """You are a document retrieval reasoning system.
You analyze the document hierarchy to find relevant sections.
Consider: title relevance, summary content, document structure.
Return scores as floats 0.0-1.0."""


class TreeSearch:
    """LLM-based tree search over PageIndex hierarchical indexes."""

    def __init__(self, lm_client):
        self.lm_client = lm_client
        self.text_extractor = TextExtractor(
            Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases"
        )

    async def search(
        self,
        query: str,
        kb_name: str,
        doc_id: Optional[str] = None,
        tree: Optional[dict] = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[dict]:
        """Search a PageIndex tree using LLM reasoning.

        Args:
            query: User query string
            kb_name: Knowledge base name
            doc_id: Specific document ID to search (optional)
            tree: Pre-loaded tree dict (optional)
            top_k: Maximum results to return
            min_score: Minimum relevance threshold

        Returns:
            List of scored result dicts with doc_id, page, section,
            summary, relevance_score, node_id, and content (raw text).
        """
        results = []

        if tree:
            scored = await self._score_tree(tree.get("doc_id", ""), tree, query)
            results.extend(scored)
        else:
            # Search across all docs in KB
            pi_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases" / kb_name / "pageindex"
            if pi_dir.exists():
                for tree_file in sorted(pi_dir.glob("*.json")):
                    if doc_id and tree_file.stem != doc_id:
                        continue
                    try:
                        loaded = json.loads(tree_file.read_text())
                    except (json.JSONDecodeError, OSError):
                        continue
                    scored = await self._score_tree(tree_file.stem, loaded, query)
                    results.extend(scored)

        # Filter by min_score, sort, take top_k
        results = [r for r in results if r.get("relevance_score", 0) >= min_score]
        results.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)
        results = results[:top_k]

        # Extract raw text for top results (REQ-RET-02)
        for result in results:
            if tree and result.get("node_id"):
                node = self._find_node_by_id(tree.get("root", {}), result["node_id"])
                if node:
                    raw_text = self.text_extractor.extract_for_node(
                        kb_name, result.get("doc_id", ""), tree, node
                    )
                    result["content"] = raw_text or ""

        return results

    async def _score_tree(
        self, doc_id: str, tree: dict, query: str
    ) -> list[dict]:
        """Score nodes in a PageIndex tree using LLM reasoning."""
        tree_json = self._serialize_tree_compact(tree.get("root", {}))
        if not tree_json:
            return []

        # Check LM health
        health_ok = await self.lm_client.check_health()
        if not health_ok:
            logger.info("LM Studio unavailable — using keyword fallback")
            return self._keyword_score(doc_id, tree, query)

        # LLM scoring
        prompt = TREE_SCORE_PROMPT.format(
            tree_json=tree_json, query=query
        )
        messages = [
            {"role": "system", "content": TREE_SCORE_FEW_SHOT_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        try:
            llm_response = await self.lm_client.stream_chat(messages=messages)
            parsed = self._parse_llm_results(llm_response or "")
            if parsed is not None:
                return self._build_results(doc_id, tree, parsed)
        except Exception as e:
            logger.warning(f"Tree search LLM call failed: {e}")

        # Fallback
        logger.info("LLM parsing failed — using keyword fallback")
        return self._keyword_score(doc_id, tree, query)

    def _serialize_tree_compact(self, node: dict, depth: int = 0) -> str:
        """Serialize tree to flat text representation (title + summary + node_id)."""
        lines = []
        indent = "  " * depth
        title = node.get("title", "")
        nid = node.get("node_id", "")
        summary = node.get("summary", "")
        page_start = node.get("page_start", 0)
        page_end = node.get("page_end", 0)

        lines.append(
            f"{indent}- [{nid}] {title} (pages {page_start}-{page_end}): {summary}"
        )
        for child in node.get("children", []):
            lines.append(self._serialize_tree_compact(child, depth + 1))
        return "\n".join(lines)

    def _parse_llm_results(self, response: str) -> Optional[list[dict]]:
        """Parse LLM JSON response into scored node list."""
        text = response.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
            if not isinstance(data, list):
                return None
            results = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                if "node_id" not in item:
                    continue
                results.append({
                    "node_id": item["node_id"],
                    "score": float(item.get("score", 0)),
                    "reason": item.get("reason", ""),
                })
            return results
        except (json.JSONDecodeError, ValueError):
            return None

    def _build_results(
        self, doc_id: str, tree: dict, scored_nodes: list[dict]
    ) -> list[dict]:
        """Map scored node_ids to result dicts using tree metadata."""
        results = []
        for scored in scored_nodes:
            node = self._find_node_by_id(
                tree.get("root", {}), scored["node_id"]
            )
            if node:
                results.append({
                    "doc_id": doc_id,
                    "page": node.get("page_start", 0),
                    "page_end": node.get("page_end", 0),
                    "section": node.get("title", ""),
                    "summary": node.get("summary", ""),
                    "relevance_score": round(scored["score"], 3),
                    "node_id": scored["node_id"],
                    "reasoning": scored.get("reason", ""),
                    "content": "",  # Filled by search() caller
                })
        return results

    def _find_node_by_id(self, node: dict, node_id: str) -> Optional[dict]:
        """Recursively find a node by its node_id."""
        if node.get("node_id") == node_id:
            return node
        for child in node.get("children", []):
            found = self._find_node_by_id(child, node_id)
            if found:
                return found
        return None

    def _keyword_score(
        self, doc_id: str, tree: dict, query: str
    ) -> list[dict]:
        """Fallback keyword scoring when LLM is unavailable."""
        results = []
        query_terms = set(query.lower().split())
        if not query_terms:
            return results

        def walk(node: dict):
            title = node.get("title", "").lower()
            summary = node.get("summary", "").lower()
            score = sum(1 for t in query_terms if t in title) * 3
            score += sum(1 for t in query_terms if t in summary)
            if score > 0:
                max_possible = len(query_terms) * 3
                relevance = score / max_possible
                results.append({
                    "doc_id": doc_id,
                    "page": node.get("page_start", 0),
                    "page_end": node.get("page_end", 0),
                    "section": node.get("title", ""),
                    "summary": node.get("summary", ""),
                    "relevance_score": round(relevance, 3),
                    "node_id": node.get("node_id", ""),
                    "reasoning": "",
                    "content": "",
                })
            for child in node.get("children", []):
                walk(child)

        walk(tree.get("root", {}))
        return results
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_tree_search.py -v
```
Expected: PASS (2/2)

- [ ] **Step 5: Add fallback and edge-case tests**

```python
@pytest.mark.asyncio
async def test_keyword_fallback_when_llm_unavailable():
    """Falls back to keyword matching when LM Studio is down."""
    from app.services.tree_search import TreeSearch
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.check_health = AsyncMock(return_value=False)

    ts = TreeSearch(lm_client=client)
    results = await ts.search(
        query="neural network",
        kb_name="test_kb",
        doc_id="test_doc",
        tree=SAMPLE_TREE,
        top_k=3,
        min_score=0.1,
    )
    # Keyword fallback should still return results for matching terms
    assert len(results) > 0


@pytest.mark.asyncio
async def test_parse_llm_results_strips_markdown():
    """Handles markdown-wrapped JSON from LLM."""
    from app.services.tree_search import TreeSearch
    from unittest.mock import AsyncMock

    client = AsyncMock()
    ts = TreeSearch(lm_client=client)

    response = "```json\n[{\"node_id\": \"node_1\", \"score\": 0.8, \"reason\": \"test\"}]\n```"
    parsed = ts._parse_llm_results(response)
    assert parsed is not None
    assert len(parsed) == 1
    assert parsed[0]["node_id"] == "node_1"
    assert parsed[0]["score"] == 0.8


@pytest.mark.asyncio
async def test_parse_llm_handles_invalid_json():
    """Returns None for invalid JSON response."""
    from app.services.tree_search import TreeSearch
    from unittest.mock import AsyncMock

    client = AsyncMock()
    ts = TreeSearch(lm_client=client)

    parsed = ts._parse_llm_results("not json at all")
    assert parsed is None


@pytest.mark.asyncio
async def test_empty_tree_returns_no_results(tree_search):
    """Search on empty tree returns empty results."""
    results = await tree_search.search(
        query="anything",
        kb_name="test_kb",
        doc_id="empty",
        tree={"doc_id": "empty", "root": {"node_id": "root", "children": []}},
        top_k=5,
        min_score=0.3,
    )
    assert results == []


def test_keyword_score_title_weights_higher():
    """Title matches score 3x more than summary matches."""
    from app.services.tree_search import TreeSearch
    from unittest.mock import AsyncMock

    tree = {
        "root": {
            "node_id": "node_a",
            "title": "Transformer Architecture",
            "summary": "Irrelevant text about cooking",
            "page_start": 0,
            "page_end": 5,
            "children": [],
        }
    }
    client = AsyncMock()
    ts = TreeSearch(lm_client=client)
    results = ts._keyword_score("doc1", tree, "transformer architecture")

    assert len(results) == 1
    # Title match: "transformer" and "architecture" both in title = 2*3 = 6
    # Summary match: 0 = 0
    # max_possible = 2 * 3 = 6
    # relevance = 6/6 = 1.0
    assert results[0]["relevance_score"] == 1.0
```

- [ ] **Step 6: Run all tests**

```bash
cd backend && python -m pytest tests/test_tree_search.py -v
```
Expected: PASS (7/7 — 2 from step 1 + 5 edge cases)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/tree_search.py backend/tests/test_tree_search.py
git commit -m "feat: add LLM-based TreeSearch service with keyword fallback

- REQ-RET-01: LLM reasons over tree summaries (no raw text)
- REQ-RET-02: Maps node_ids to page ranges via TextExtractor
- Fallback to keyword scoring when LM unavailable
- Parses LLM JSON with markdown fence handling"
```

---

### Task 3: VectorKB Service (stub for now, ready for FR-1.3)

**Files:**
- Create: `backend/app/services/vector_kb.py`
- Test: `backend/tests/test_vector_kb.py`

This service provides the interface for vector-based retrieval. Since the Vector KB builder (FR-1.3) doesn't exist yet, this returns empty results but implements the full RRF merge logic so hybrid/naive will work when data arrives.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_vector_kb.py
"""Vector KB service tests."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

VECTOR_BASE = Path("data/knowledge_bases")


def test_naive_search_returns_empty_when_no_vectors():
    """Returns empty list when vector data doesn't exist."""
    from app.services.vector_kb import VectorKBService

    svc = VectorKBService(VECTOR_BASE)
    result = svc.naive_search("query", "nonexistent_kb", top_k=5)
    assert result == []


def test_hybrid_search_returns_empty_when_no_vectors():
    """Returns empty list when vector data doesn't exist."""
    from app.services.vector_kb import VectorKBService

    svc = VectorKBService(VECTOR_BASE)
    result = svc.hybrid_search("query", "nonexistent_kb", top_k=5)
    assert result == []


def test_rrf_merge_combines_two_rankings():
    """RRF correctly merges vector and keyword results."""
    from app.services.vector_kb import VectorKBService, _rrf_merge

    vector_results = [
        {"doc_id": "d1", "section": "A", "content": "vector match 1"},
        {"doc_id": "d2", "section": "B", "content": "vector match 2"},
        {"doc_id": "d3", "section": "C", "content": "vector match 3"},
    ]
    keyword_results = [
        {"doc_id": "d2", "section": "B", "content": "keyword match 2"},
        {"doc_id": "d4", "section": "D", "content": "keyword match 4"},
    ]

    merged = _rrf_merge(vector_results, keyword_results, top_k=5)

    # d2 appears in both, should rank highest
    assert len(merged) > 0
    top_ids = [r["doc_id"] for r in merged]
    # d2 should be first (appears in both lists)
    assert top_ids[0] == "d2"


def test_keyword_search_over_text_files():
    """Keyword search finds matches in raw text files."""
    from app.services.vector_kb import VectorKBService
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a text file with known content
        Path(tmpdir).mkdir(parents=True, exist_ok=True)
        (Path(tmpdir) / "doc1.txt").write_text(
            "Machine learning is a subset of artificial intelligence. "
            "Neural networks are used for deep learning applications."
        )
        (Path(tmpdir) / "doc2.txt").write_text(
            "Data science involves statistics and probability. "
            "Machine learning models require training data."
        )

        svc = VectorKBService(VECTOR_BASE)
        results = svc._keyword_search_in_directory(
            "machine learning", Path(tmpdir), top_k=3
        )

        assert len(results) > 0
        # Both files mention "machine learning", doc1 should rank higher
        # (has "neural networks" and "deep learning" as extra terms)
        assert all("score" in r for r in results)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_vector_kb.py -v
```
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write implementation**

```python
"""VectorKBService — vector and keyword retrieval over knowledge bases.

Provides interfaces for:
- naive_search: Pure vector similarity (returns empty until FR-1.3)
- hybrid_search: Vector + keyword RRF merge (returns empty until FR-1.3)
- keyword_search: BM25-style search over raw document text

When vector data is unavailable (FR-1.3 not implemented), returns empty
results with an info log. Interface is ready for when data arrives.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

UPLOAD_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases" / "uploads"


class VectorKBService:
    """Vector and keyword retrieval service."""

    def __init__(self, kb_base: Path):
        self.kb_base = kb_base

    def naive_search(
        self, query: str, kb_name: str, top_k: int = 5, min_score: float = 0.3
    ) -> list[dict]:
        """Pure vector similarity search."""
        vector_dir = self.kb_base / kb_name / "vectors"
        if not vector_dir.exists() or not any(vector_dir.iterdir()):
            logger.info(
                f"VectorKB: no vector data in {vector_dir}, "
                "returning empty results for naive search"
            )
            return []

        # When FR-1.3 (Vector KB Builder) creates vector data:
        # 1. Embed the query
        # 2. Compute cosine similarity against all stored vectors
        # 3. Return top_k above min_score
        return []

    def hybrid_search(
        self, query: str, kb_name: str, top_k: int = 5, min_score: float = 0.3
    ) -> list[dict]:
        """Hybrid vector + keyword retrieval with RRF merge."""
        vector_results = self.naive_search(query, kb_name, top_k * 2, min_score)
        keyword_results = self._keyword_search(query, kb_name, top_k * 2)

        if not vector_results and not keyword_results:
            return []

        return _rrf_merge(vector_results, keyword_results, top_k)

    def keyword_search(
        self, query: str, kb_name: str, top_k: int = 5
    ) -> list[dict]:
        """Pure keyword search over raw document text."""
        return self._keyword_search(query, kb_name, top_k)

    def _keyword_search(
        self, query: str, kb_name: str, top_k: int
    ) -> list[dict]:
        """Search over uploaded document files."""
        upload_dir = UPLOAD_BASE / kb_name
        if not upload_dir.exists():
            return []

        return self._keyword_search_in_directory(query, upload_dir, top_k)

    def _keyword_search_in_directory(
        self, query: str, search_dir: Path, top_k: int
    ) -> list[dict]:
        """Search all text files in a directory."""
        query_terms = set(query.lower().split())
        if not query_terms:
            return []

        results = []

        for file_path in search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix not in (".txt", ".md", ".pdf"):
                continue

            try:
                if file_path.suffix == ".pdf":
                    import fitz
                    doc = fitz.open(str(file_path))
                    text = "\n".join(
                        page.get_text("text") for page in doc
                    )
                    doc.close()
                else:
                    text = file_path.read_text(encoding="utf-8")
            except (OSError, Exception):
                continue

            score = sum(
                1 for t in query_terms if t in text.lower()
            )
            if score > 0:
                max_possible = len(query_terms)
                results.append({
                    "doc_id": file_path.stem,
                    "section": file_path.name,
                    "content": text[:500],
                    "relevance_score": round(score / max_possible, 3),
                    "page": 0,
                    "page_end": 0,
                    "node_id": "",
                })

        results.sort(
            key=lambda r: r.get("relevance_score", 0), reverse=True
        )
        return results[:top_k]


def _rrf_merge(
    vector_results: list[dict],
    keyword_results: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """Reciprocal Rank Fusion merge of two ranked result lists.

    Uses default k=60 as established in RRF literature.
    Deduplicates by (doc_id, section) key, keeping higher RRF score.
    """
    k = 60

    # Compute ranks
    scores: dict[tuple, tuple[float, dict]] = {}

    def process(results: list[dict]):
        for rank, result in enumerate(results):
            key = (result.get("doc_id", ""), result.get("section", ""))
            rrf = 1.0 / (k + rank + 1)

            if key in scores:
                old_score, old_result = scores[key]
                if rrf > old_score:
                    scores[key] = (rrf, result)
            else:
                scores[key] = (rrf, result)

    process(vector_results)
    process(keyword_results)

    merged = []
    for key, (rrf_score, result) in scores.items():
        r = dict(result)
        r["rrf_score"] = round(rrf_score, 4)
        r["relevance_score"] = round(rrf_score, 4)
        merged.append(r)

    merged.sort(key=lambda r: r.get("rrf_score", 0), reverse=True)
    return merged[:top_k]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_vector_kb.py -v
```
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/vector_kb.py backend/tests/test_vector_kb.py
git commit -m "feat: add VectorKBService with RRF hybrid merge and keyword search

- Stub for vector operations (returns empty until FR-1.3)
- Working keyword search over uploaded documents
- Reciprocal Rank Fusion merge for hybrid retrieval
- Ready interface for when vector KB builder creates data"
```

---

### Task 4: Improve Query Router

**Files:**
- Modify: `backend/app/services/query_router.py`
- Test: `backend/tests/test_query_router.py`

Current query_router.py uses length heuristics. We add: complexity-aware routing, fallback logic when data sources are missing, and integration with the complexity scorer.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_query_router.py
"""Query router tests — pipeline selection with complexity awareness."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_explicit_pipeline_is_respected():
    """Explicit pipeline parameter always wins."""
    from app.services.query_router import route_query

    result = route_query(
        "anything", "kb", doc_id=None, retrieval_pipeline="hybrid"
    )
    assert result == "hybrid"

    result = route_query(
        "anything", "kb", doc_id=None, retrieval_pipeline="naive"
    )
    assert result == "naive"


def test_doc_id_routes_to_tree():
    """When doc_id is specified, tree search for precision."""
    from app.services.query_router import route_query

    result = route_query("query", "kb", doc_id="specific_doc")
    assert result == "tree"


def test_short_query_routes_to_hybrid_when_vectors_exist():
    """Short, broad queries go to hybrid for recall."""
    from app.services.query_router import route_query, RouteContext

    ctx = RouteContext(has_trees=True, has_vectors=True, complexity=0.2)
    result = route_query("data", "kb", context=ctx)
    assert result in ("hybrid", "combined")  # depends on implementation


def test_complex_query_routes_to_tree():
    """Long or specific queries go to tree for precision."""
    from app.services.query_router import route_query

    result = route_query(
        "What are the key differences between supervised and "
        "unsupervised learning approaches in deep neural networks?",
        "kb",
    )
    assert result == "tree"


def test_no_data_sources_returns_tree_with_warning():
    """When no vectors exist, fall back to tree."""
    from app.services.query_router import route_query, RouteContext

    ctx = RouteContext(has_trees=True, has_vectors=False)
    result = route_query("short query", "kb", context=ctx)
    # Should fall back to tree since no vectors
    assert result == "tree"


def test_no_treeses_falls_back_to_naive():
    """When no PageIndex trees exist, fall back to naive/hybrid."""
    from app.services.query_router import route_query, RouteContext

    ctx = RouteContext(has_trees=False, has_vectors=True)
    result = route_query("query", "kb", context=ctx)
    # Should use available retrieval
    assert result in ("hybrid", "naive")


def test_unknown_pipeline_defaults_to_tree():
    """Invalid pipeline parameter defaults to tree."""
    from app.services.query_router import route_query

    result = route_query("q", "kb", retrieval_pipeline="banana")
    assert result == "tree"
```

- [ ] **Step 2: Run test to verify failures**

```bash
cd backend && python -m pytest tests/test_query_router.py -v
```
Expected: FAIL (RouteContext not defined, context parameter missing)

- [ ] **Step 3: Rewrite query_router.py**

```python
"""Query Router — retrieval mode selector with complexity awareness.

Routes queries to appropriate pipeline (tree/hybrid/naive/combined) based on:
- Explicit pipeline parameter (always wins)
- Document targeting (doc_id → tree)
- Available data sources (no vectors → tree, no trees → naive)
- Query complexity (from ComplexityScorer)
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

VALID_PIPELINES = {"tree", "hybrid", "naive", "combined"}


@dataclass
class RouteContext:
    """Context for routing decisions."""
    has_trees: bool = True
    has_vectors: bool = False
    complexity: float = 0.5
    doc_pages: int = 0


def route_query(
    query: str,
    kb_name: str,
    doc_id: Optional[str] = None,
    retrieval_pipeline: Optional[str] = None,
    context: Optional[RouteContext] = None,
) -> str:
    """Determine the best retrieval pipeline for a query.

    Returns pipeline name: "tree", "hybrid", "naive", or "combined".
    """
    # Explicit override wins
    if retrieval_pipeline:
        if retrieval_pipeline not in VALID_PIPELINES:
            logger.warning(
                f"Unknown retrieval pipeline '{retrieval_pipeline}', "
                f"defaulting to 'tree'"
            )
            return "tree"
        return retrieval_pipeline

    ctx = context or RouteContext()

    # If specific document targeted → tree
    if doc_id:
        return "tree"

    # Check data source availability
    if not ctx.has_trees and ctx.has_vectors:
        logger.warning("No PageIndex trees — falling back to vector search")
        return "hybrid"

    if not ctx.has_trees and not ctx.has_vectors:
        logger.warning("No retrieval data available")
        return "tree"

    # Complexity-aware routing
    query_terms = len(query.split())

    if ctx.complexity > 0.6:
        # High complexity → tree for precision
        return "tree"
    elif ctx.complexity < 0.3:
        if query_terms <= 3:
            # Short, simple → hybrid for recall
            return "hybrid" if ctx.has_vectors else "tree"
        else:
            return "tree"
    else:
        # Medium complexity → combined when both sources available
        if ctx.has_trees and ctx.has_vectors:
            return "combined"
        elif ctx.has_trees:
            return "tree"
        else:
            return "hybrid"
```

- [ ] **Step 4: Run tests to verify passes**

```bash
cd backend && python -m pytest tests/test_query_router.py -v
```
Expected: PASS (7/7)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/query_router.py backend/tests/test_query_router.py
git commit -m "feat: improve Query Router with complexity awareness and fallback

- RouteContext: has_trees, has_vectors, complexity signals
- Falls back to available data sources
- Explicit pipeline parameter always wins
- Unknown pipeline defaults to tree"
```

---

### Task 5: Rewrite Retrieval Routes

**Files:**
- Modify: `backend/app/routers/retrieval.py` (full rewrite)
- Test: `backend/tests/test_retrieval.py`

Now wire everything together. The route delegates to TreeSearch, VectorKBService, and QueryRouter instead of doing inline work.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_retrieval.py
"""Retrieval route integration tests."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import json


def create_test_app():
    """Create a minimal FastAPI test app with retrieval router."""
    from fastapi import FastAPI
    from app.routers.retrieval import router as retrieval_router

    app = FastAPI()
    app.include_router(retrieval_router)
    return app


@pytest.fixture
def client():
    return TestClient(create_test_app())


@pytest.mark.asyncio
async def test_retrieve_with_tree_pipeline(client):
    """POST /retrieve with tree pipeline returns scored results."""
    mock_tree = {
        "doc_id": "test_doc",
        "title": "Test",
        "total_pages": 5,
        "root": {
            "node_id": "root",
            "title": "Test",
            "summary": "A test document",
            "page_start": 0,
            "page_end": 4,
            "children": [],
        },
    }

    with patch("app.routers.retrieval._load_pageindex_tree", return_value=mock_tree):
        response = client.post("/api/v1/retrieve", json={
            "query": "test query",
            "kb_name": "test_kb",
            "retrieval_pipeline": "tree",
            "top_k": 3,
        })

    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_used"] == "tree"
    assert "results" in data
    assert "retrieval_latency_ms" in data


@pytest.mark.asyncio
async def test_retrieve_returns_empty_for_missing_kb(client):
    """Returns zero results for nonexistent KB."""
    response = client.post("/api/v1/retrieve", json={
        "query": "anything",
        "kb_name": "nonexistent",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
    assert data["pipeline_used"] == "tree"


@pytest.mark.asyncio
async def test_query_http_returns_answer(client):
    """POST /query returns structured answer with citations."""
    mock_tree = {
        "doc_id": "doc1",
        "title": "Doc1",
        "total_pages": 3,
        "root": {
            "node_id": "root",
            "title": "Doc1",
            "summary": "Machine learning basics",
            "page_start": 0,
            "page_end": 2,
            "children": [],
        },
    }

    with patch("app.routers.retrieval._load_pageindex_tree", return_value=mock_tree):
        with patch("app.routers.retrieval.lm_client") as mock_lm:
            mock_lm.check_health = AsyncMock(return_value=True)
            mock_lm.stream_chat = AsyncMock(
                return_value="Machine learning is a field of AI."
            )
            response = client.post("/api/v1/query", json={
                "query": "What is machine learning?",
                "kb_name": "test_kb",
            })

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert "complexity_score" in data
    assert "e2e_latency_ms" in data
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd backend && python -m pytest tests/test_retrieval.py -v
```
Expected: FAIL (imports and structure won't match)

- [ ] **Step 3: Rewrite retrieval.py**

```python
"""Retrieval routes: POST /retrieve, POST /query."""

import logging
import time
from typing import Optional
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["retrieval"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases"

# Service instances — lazy-initialized per request


def _get_tree_search():
    from app.main import lm_client
    from app.services.tree_search import TreeSearch
    return TreeSearch(lm_client=lm_client)


def _get_vector_kb():
    from app.services.vector_kb import VectorKBService
    return VectorKBService(DATA_DIR)


def _load_pageindex_tree(kb_name: str, doc_id: str) -> dict | None:
    """Load a PageIndex tree from disk."""
    tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
    if tree_path.exists():
        import json
        return json.loads(tree_path.read_text())
    return None


def _list_pageindex_docs(kb_name: str) -> list[str]:
    """List all PageIndex document IDs in a KB."""
    tree_dir = DATA_DIR / kb_name / "pageindex"
    if not tree_dir.exists():
        return []
    return [f.stem for f in tree_dir.glob("*.json")]


# ── Request/Response Schemas

class RetrieveRequest(BaseModel):
    query: str
    kb_name: str
    doc_id: Optional[str] = None
    retrieval_pipeline: str = "tree"
    top_k: int = 5
    min_score: float = 0.3


class QueryRequest(BaseModel):
    query: str
    kb_name: str
    mode: str = "auto"
    retrieval_pipeline: str = "tree"
    session_id: str = ""
    doc_id: Optional[str] = None


class RetrieveResult(BaseModel):
    query: str
    pipeline_used: str
    results: list[dict]
    retrieval_latency_ms: float
    model_tier_used: int
    total_candidates_scored: int


# ── POST /api/v1/retrieve

@router.post("/retrieve")
async def retrieve_endpoint(req: RetrieveRequest):
    start = time.time()

    # Check data availability
    tree_docs = _list_pageindex_docs(req.kb_name)
    from app.services.query_router import RouteContext

    ctx = RouteContext(
        has_trees=bool(tree_docs),
        has_vectors=False,  # Will be updated when FR-1.3 creates vectors
        complexity=0.5,
        doc_pages=0,
    )

    # Route query
    from app.services.query_router import route_query
    pipeline = route_query(
        query=req.query,
        kb_name=req.kb_name,
        doc_id=req.doc_id,
        retrieval_pipeline=req.retrieval_pipeline,
        context=ctx,
    )

    results = []
    total_candidates = 0

    if pipeline == "tree":
        tree_search = _get_tree_search()
        tree = None
        if req.doc_id:
            tree = _load_pageindex_tree(req.kb_name, req.doc_id)
            if tree:
                results = await tree_search.search(
                    query=req.query,
                    kb_name=req.kb_name,
                    doc_id=req.doc_id,
                    tree=tree,
                    top_k=req.top_k,
                    min_score=req.min_score,
                )
                total_candidates = len(tree_search._keyword_score(
                    req.doc_id, tree, req.query
                ))
        else:
            # Search all docs
            for doc_id in tree_docs:
                t = _load_pageindex_tree(req.kb_name, doc_id)
                if t:
                    doc_results = await tree_search.search(
                        query=req.query,
                        kb_name=req.kb_name,
                        doc_id=doc_id,
                        tree=t,
                        top_k=req.top_k,
                        min_score=req.min_score,
                    )
                    results.extend(doc_results)
                    total_candidates += len(tree_search._keyword_score(
                        doc_id, t, req.query
                    ))

    elif pipeline in ("hybrid", "naive"):
        vector_kb = _get_vector_kb()
        if pipeline == "hybrid":
            results = vector_kb.hybrid_search(
                query=req.query,
                kb_name=req.kb_name,
                top_k=req.top_k,
                min_score=req.min_score,
            )
        else:
            results = vector_kb.naive_search(
                query=req.query,
                kb_name=req.kb_name,
                top_k=req.top_k,
                min_score=req.min_score,
            )

    elif pipeline == "combined":
        # Tree search + vector search, merged
        tree_search = _get_tree_search()
        vector_kb = _get_vector_kb()

        # Tree results
        tree_results = []
        if req.doc_id:
            tree = _load_pageindex_tree(req.kb_name, req.doc_id)
            if tree:
                tree_results = await tree_search.search(
                    query=req.query, kb_name=req.kb_name,
                    doc_id=req.doc_id, tree=tree, top_k=req.top_k,
                    min_score=req.min_score,
                )
        else:
            for doc_id in tree_docs:
                t = _load_pageindex_tree(req.kb_name, doc_id)
                if t:
                    tr = await tree_search.search(
                        query=req.query, kb_name=req.kb_name,
                        doc_id=doc_id, tree=t, top_k=req.top_k,
                        min_score=req.min_score,
                    )
                    tree_results.extend(tr)

        # Vector results
        vector_results = vector_kb.naive_search(
            query=req.query, kb_name=req.kb_name, top_k=req.top_k
        )

        # Merge: tree results first, then vector, dedup by (doc_id, page)
        seen = set()
        for r in tree_results + vector_results:
            key = (r.get("doc_id", ""), r.get("page", 0), r.get("node_id", ""))
            if key not in seen:
                seen.add(key)
                results.append(r)
        results = results[:req.top_k]

    elapsed = (time.time() - start) * 1000

    return {
        "query": req.query,
        "pipeline_used": pipeline,
        "results": results,
        "retrieval_latency_ms": round(elapsed, 1),
        "model_tier_used": 2,
        "total_candidates_scored": total_candidates,
    }


# ── POST /api/v1/query

@router.post("/query")
async def query_endpoint(req: QueryRequest):
    """HTTP Q&A fallback — non-streaming."""
    start = time.time()

    session_id = req.session_id or f"solve_{int(time.time())}"
    solve_dir = f"data/user/solve/{session_id}"
    agent_steps = []

    # 1. Retrieve context via tree search
    tree_search = _get_tree_search()
    tree = None
    if req.doc_id:
        tree = _load_pageindex_tree(req.kb_name, req.doc_id)

    retrieve_results = await tree_search.search(
        query=req.query,
        kb_name=req.kb_name,
        doc_id=req.doc_id,
        tree=tree,
        top_k=5,
        min_score=0.3,
    )

    context_parts = []
    for r in retrieve_results:
        content = r.get("content", r.get("summary", ""))
        context_parts.append(
            f"[{r.get('section', '')}] (doc:{r.get('doc_id', '')}, "
            f"p.{r.get('page', '')}): {content}"
        )
    context = "\n\n".join(context_parts)

    agent_steps.append({
        "agent": "retrieve",
        "content": f"Found {len(retrieve_results)} relevant sections",
        "timestamp": time.time(),
    })

    # 2. Complexity scoring
    from app.services.complexity_scorer import score_query_complexity
    score, tier = score_query_complexity(
        query_text=req.query,
        retrieved_chunks=len(retrieve_results),
        doc_size=len(context),
    )

    agent_steps.append({
        "agent": "route",
        "content": f"Complexity: {score:.2f} → Tier {tier}",
        "timestamp": time.time(),
    })

    # 3. Generate answer
    from app.main import lm_client, model_manager
    citations = []
    answer_content = ""

    health_ok = await lm_client.check_health()

    if health_ok:
        context_section = f"\n\nContext from documents:\n{context}" if context else ""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert document intelligence assistant. "
                    "Answer based on the provided context. If insufficient "
                    "information, say so clearly."
                ),
            },
            {"role": "user", "content": f"{req.query}{context_section}"},
        ]

        answer_content = await lm_client.stream_chat(
            messages=messages, max_tokens=4096
        ) or "No response generated."

        for r in retrieve_results:
            citations.append({
                "doc_id": r["doc_id"],
                "page": r["page"],
                "section": r.get("section", ""),
                "node_id": r.get("node_id", ""),
            })

        agent_steps.append({
            "agent": "solve",
            "content": answer_content[:300],
            "timestamp": time.time(),
        })
    else:
        answer_content = (
            f"LM Studio is not available. Query: {req.query}\n\n"
            f"Retrieved {len(retrieve_results)} sections for context."
        )

    elapsed = (time.time() - start) * 1000

    return {
        "answer": answer_content,
        "citations": citations,
        "agent_steps": agent_steps,
        "model_tier_used": tier,
        "complexity_score": round(score, 3),
        "e2e_latency_ms": round(elapsed, 1),
        "session_id": session_id,
        "solve_dir": solve_dir,
    }
```

- [ ] **Step 4: Fix import for lm_client in route handler**

The route uses `from app.main import lm_client` for query endpoint. This needs the module to be importable during tests. We handle this with mock patches in the test.

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest tests/test_retrieval.py -v
```
Expected: PASS (3/3)

- [ ] **Step 6: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: ALL PASS (at least 15+ existing + 16 new = 31+)

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/retrieval.py backend/tests/test_retrieval.py
git commit -m "feat: rewrite retrieval routes with service-based architecture

- POST /retrieve: delegates to TreeSearch, VectorKBService, QueryRouter
- POST /query: uses TreeSearch for context + LLM for answers
- Combined mode: merges tree + vector results with dedup
- Full integration test coverage"
```

---

### Task 6: Wire services into main.py

**Files:**
- Modify: `backend/app/main.py`

Add TextExtractor and VectorKBService as optional service instances accessible by routes.

- [ ] **Step 1: Add service wiring**

Add after the `pageindex_generator` line in `main.py`:

```python
# ... existing code ...
pageindex_generator = PageIndexTreeGenerator(lm_client)
benchmark_runner = BenchmarkRunner(lm_client, vram_monitor, model_manager)
```

No changes needed to main.py — services are lazily instantiated in routes via helper functions (`_get_tree_search()`, `_get_vector_kb()`). This avoids circular imports.

- [ ] **Step 2: Verify imports work**

```bash
cd backend && python -c "from app.routers.retrieval import router; print('import OK')"
cd backend && python -c "from app.services.tree_search import TreeSearch; print('import OK')"
cd backend && python -c "from app.services.text_extractor import TextExtractor; print('import OK')"
cd backend && python -c "from app.services.vector_kb import VectorKBService; print('import OK')"
cd backend && python -c "from app.services.query_router import route_query, RouteContext; print('import OK')"
```

Expected: All print "import OK"

- [ ] **Step 3: Run full test suite**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "chore: verify retrieval services import correctly"
```

---

### Task 7: Update STATUS.md and integration verification

**Files:**
- Modify: `docs/superpowers/STATUS.md`

Update all feature status tables to reflect the completed Retrieval Layer.

- [ ] **Step 1: Update STATUS.md**

Key changes to STATUS.md:
- Query Router: ❌ TODO → ✅ Done
- Hybrid RAG: ❌ TODO → 🟨 Partial (interface ready, stubs for data)
- Add Tree Search: ✅ Done
- Add Text Extractor: ✅ Done
- Add Vector KB: 🟨 Partial (interface ready, no data)
- POST /retrieve: ❌ TODO → ✅ Done
- POST /query: ❌ TODO → ✅ Done
- Delete doc: ✅ Done (was already in Task 3 of telemetry plan, already implemented)
- Test coverage: update totals
- Add Retrieval Layer to the Feature Implementation Matrix

- [ ] **Step 2: Run final test suite**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs: update STATUS.md with Retrieval Layer completion

- Tree Search (LLM-based) ✅
- Query Router (improved) ✅
- Text Extractor ✅
- Vector KB (interface stub) 🟨
- POST /retrieve ✅
- POST /query ✅"
```

---

## Non-Goals (Deferred)

| Item | Reason | Future Plan |
|------|--------|-------------|
| Vector KB Builder (FR-1.3) | Embedding pipeline + chunking + storage | Separate plan |
| OpenTelemetry instrumentation | Phase 9 | Telemetry plan |
| Smart Solver dual-loop integration | Full agent pipeline | Separate plan |
| Re-ranking with cross-encoder | VRAM cost not justified | Future optimization |
| Vision-based indexing | PageIndex image processing | Future enhancement |

## Test Summary

| File | Tests |
|------|-------|
| `test_text_extractor.py` | 4 — page extraction, missing files, out-of-range, missing doc |
| `test_tree_search.py` | 7 — scoring, doc_id filter, fallback, markdown parsing, invalid JSON, empty tree, keyword weights |
| `test_vector_kb.py` | 4 — empty results, RRF merge, keyword search |
| `test_query_router.py` | 7 — explicit pipeline, doc_id, complexity, fallback |
| `test_retrieval.py` | 3 — retrieve tree, missing KB, query answer |
| **Total new** | **25** |
| **Total project** | **14 existing + 25 = 39** |
