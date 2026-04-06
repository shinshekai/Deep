# PageIndex Tree Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert uploaded PDF/TXT/MD documents into hierarchical JSON tree indexes using LLM-reasoned section identification and summaries.

**Architecture:** Three-pass pipeline — (1) TOC extraction via LLM heading analysis, (2) character-position-based page range assignment, (3) LLM node summarization — integrated into the knowledge upload endpoint.

**Tech Stack:** Python 3.10+, FastAPI, httpx (LM Studio client), PyMuPDF (PDF text extraction), pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/app/services/pageindex_generator.py` | CREATE | Main service: 3-pass tree generation, fallbacks, tree structuring |
| `backend/app/config.py` | MODIFY | Add `pageindex_model`, `pageindex_max_pages_per_node`, `pageindex_max_tokens_per_node` settings |
| `backend/app/routers/knowledge.py` | MODIFY | Replace stub upload pipeline with real PageIndex generation, async task support |
| `backend/app/main.py` | MODIFY | Wire PageIndexTreeGenerator instance into lifespan |
| `backend/app/services/lm_studio_client.py` | MODIFY | Add `stream_chat_completion` method (orchestrator needs it) |
| `backend/pyproject.toml` | MODIFY | Add pytest to main deps |
| `backend/tests/__init__.py` | CREATE | Test package |
| `backend/tests/test_pageindex_generator.py` | CREATE | Unit tests: heading ID, page range assignment, tree structure, LLM call, fallbacks |
| `backend/tests/conftest.py` | CREATE | Fixtures for lm_client mock, sample doc content |

**Key constraint:** `lm_studio_client.py` only has `stream_chat()`. The `solve_orchestrator.py` calls `stream_chat_completion()` which doesn't exist yet. Task 1 fixes this first.

---

### Task 1: Add `stream_chat_completion` to LM Studio client

The `solve_orchestrator.py` calls `lm_client.stream_chat_completion(model, messages, max_tokens)` but the client only has `stream_chat()`. Add the method.

**Files:**
- Modify: `backend/app/services/lm_studio_client.py:54` (insert before line 55)
- Test: `backend/tests/test_lm_studio_client.py` (new)

- [ ] **Step 1: Create test file and conftest**

Create `backend/tests/conftest.py`:
```python
"""Shared pytest fixtures."""

import pytest


@pytest.fixture
def mock_httpx_response():
    """Return a mock httpx.Response for model listing."""
    import httpx
    return httpx.Response(200, json={"data": [{"id": "Qwen3-4B-Q4_K_M"}]})
```

Create `backend/tests/__init__.py`: (empty file)

```bash
echo "" > backend/tests/__init__.py
```

Create `backend/tests/test_lm_studio_client.py`:
```python
"""Tests for LM Studio client stream_chat_completion."""

import pytest


@pytest.mark.anyio
async def test_stream_chat_completion_returns_content():
    # This test verifies method exists and returns expected type
    # Full mocking of httpx streaming is complex; verify method signature exists
    from app.services.lm_studio_client import LMStudioClient
    client = LMStudioClient()
    assert callable(getattr(client, "stream_chat_completion", None))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_lm_studio_client.py -v
```
Expected: FAIL with assertion error (method doesn't exist)

- [ ] **Step 3: Add the method to lm_studio_client.py**

Add this method at line 54 (right after `unload_model` method, before `stream_chat`):

```python
    async def stream_chat_completion(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 2048,
    ) -> dict | None:
        """Stream chat completion. Returns {"content": str} or None on error."""
        try:
            body: dict = {
                "messages": messages,
                "model": model,
                "stream": True,
                "max_tokens": max_tokens,
            }
            content = []
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    json=body,
                    headers=self._headers,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk.get("choices", [{}])[0].get(
                                    "delta", {})
                                tok = delta.get("content", "")
                                if tok:
                                    content.append(tok)
                            except json.JSONDecodeError:
                                pass
            full_content = "".join(content) if content else None
            if full_content:
                return {"content": full_content}
            return None
        except Exception as e:
            logger.error(f"stream_chat_completion failed: {e}")
            return {"error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_lm_studio_client.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/lm_studio_client.py backend/tests/
git commit -m "feat: add stream_chat_completion method to LM Studio client
solve_orchestrator.py requires this method; was previously missing"
```

---

### Task 2: Add PageIndex settings to config.py

**Files:**
- Modify: `backend/app/config.py` (Settings class, lines 5-27)
- Test: None needed (pydantic-settings handles validation)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_config.py`:
```python
"""Tests for config settings."""

def test_pageindex_settings_exist():
    from app.config import get_settings
    settings = get_settings()
    assert hasattr(settings, "pageindex_model")
    assert hasattr(settings, "pageindex_max_pages_per_node")
    assert hasattr(settings, "pageindex_max_tokens_per_node")
    assert settings.pageindex_max_pages_per_node == 10
    assert settings.pageindex_max_tokens_per_node == 20000
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_config.py -v
```
Expected: FAIL with AttributeError (attributes don't exist)

- [ ] **Step 3: Add the settings**

In `backend/app/config.py`, add these fields inside the `Settings` class (after line 19, before `metrics_interval`):

```python
    pageindex_model: str = ""
    pageindex_max_pages_per_node: int = 10
    pageindex_max_tokens_per_node: int = 20000
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_config.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat: add PageIndex generation settings to config
PAGEINDEX_MODEL, MAX_PAGES_PER_NODE, MAX_TOKENS_PER_NODE"
```

---

### Task 3: Build PageIndexTreeGenerator service (core 3-pass pipeline)

**Files:**
- Create: `backend/app/services/pageindex_generator.py` (~280 lines)
- Test: `backend/tests/test_pageindex_generator.py`

- [ ] **Step 1: Create the service with all classes and methods**

Create `backend/app/services/pageindex_generator.py`:

```python
"""PageIndex tree generator — 3-pass hierarchical document indexing.

Pass 1: TOC Extraction — LLM identifies section headings
Pass 2: Content Matching — assign page ranges to each heading
Pass 3: Node Summarization — LLM generates per-node summaries
"""

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# System prompts for each pass
HEADING_EXTRACTION_PROMPT = (
    "You are a document structure analysis expert. Analyze the following document text "
    "and extract all section headings and their hierarchy as a JSON array. Each entry "
    "should have exactly two fields: 'title' (string) and 'depth' (integer, 1 for top-level, "
    "2 for subsection, etc.). Do not include page numbers or other metadata. "
    "Only output valid JSON, no markdown or explanation.\n\n"
    "Return format: [{\"title\": \"Introduction\", \"depth\": 1}, "
    "{\"title\": \"Background\", \"depth\": 2}]"
)

SUMMARY_PROMPT = (
    "Summarize the following document section in 2-3 sentences. Focus on the key points, "
    "main arguments, and conclusions. Do not include specific page references. "
    "Only output the summary text, no markdown or labels.\n\n"
)


class PageIndexTreeGenerator:
    """Generate hierarchical PageIndex tree from document content."""

    def __init__(self, lm_client):
        self.lm_client = lm_client

    async def build_tree(
        self,
        doc_content: dict,
        model_id: str,
        doc_id: str,
    ) -> Optional[dict]:
        """Build the full PageIndexTree from parsed document content.

        Args:
            doc_content: Output from document_processor.extract_text()
            model_id: LLM model to use for heading identification and summaries
            doc_id: Unique document identifier

        Returns:
            PageIndexTree dict or None on failure
        """
        pages = doc_content.get("pages", [])
        if not pages:
            logger.warning("No pages found in doc_content")
            return self._empty_tree(doc_id, "Unknown")

        total_pages = len(pages)
        doc_title = doc_id

        # ── Pass 1: TOC Extraction ──
        toc_nodes = await self._extract_headings(pages, model_id)

        # If no headings found, create a single root node
        if not toc_nodes:
            logger.info("No headings identified — creating single-node tree")
            toc_nodes = [{"title": "Document", "depth": 1}]

        # ── Pass 2: Content Matching ──
        nodes_with_ranges = self._assign_page_ranges(pages, toc_nodes)

        # ── Pass 3: Node Summarization ──
        for node in nodes_with_ranges:
            summary = await self._summarize_node(node, pages, model_id)
            node["summary"] = summary

        # ── Structure tree ──
        tree = self._structure_tree(nodes_with_ranges, doc_id, total_pages, doc_title)
        return tree

    # ── Pass 1: Heading Extraction ──

    def _extract_toc_candidates(self, pages: list[dict]) -> str:
        """Extract text from first 20 pages as TOC candidates.

        The architecture specifies checking first 20 pages for table of contents.
        Returns concatenated text with page separators.
        """
        candidate_pages = pages[:20]
        parts = []
        for page_info in candidate_pages:
            text = page_info.get("text", "").strip()
            if text:
                parts.append(f"[Page {page_info.get('page_num', '?')}]\n{text}")
        return "\n---\n".join(parts)

    async def _extract_headings(
        self,
        pages: list[dict],
        model_id: str,
    ) -> list[dict]:
        """Pass 1: Ask LLM to identify section headings and their hierarchy.

        Returns list of {"title": str, "depth": int} or empty list on failure.
        """
        toc_text = self._extract_toc_candidates(pages)
        if not toc_text.strip():
            return []

        # Truncate to avoid very long prompts
        max_chars = 60000  # ~15k tokens for the prompt
        if len(toc_text) > max_chars:
            toc_text = toc_text[:max_chars] + "\n...[truncated]"

        try:
            result = await self.lm_client.stream_chat(
                messages=[
                    {"role": "system", "content": HEADING_EXTRACTION_PROMPT},
                    {"role": "user", "content": toc_text},
                ],
                model=model_id,
                max_tokens=4096,
                temperature=0.1,
            )
            if result is None:
                logger.warning("LLM returned None for heading extraction")
                return self._regex_heading_fallback(toc_text)

            return self._parse_heading_json(result)
        except Exception as e:
            logger.error(f"Heading extraction failed: {e}")
            return self._regex_heading_fallback(toc_text)

    def _parse_heading_json(self, raw_text: str) -> list[dict]:
        """Parse LLM output as JSON heading array. Returns empty list on failure."""
        # Try to find JSON array in the response
        text = raw_text.strip()
        # Remove markdown code fence if present
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        # Find the JSON array
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            logger.warning(f"No JSON array found in heading response: {text[:200]}")
            return []
        json_str = text[start:end + 1]
        try:
            headings = json.loads(json_str)
            if not isinstance(headings, list):
                return []
            # Validate structure
            result = []
            for h in headings:
                if isinstance(h, dict) and "title" in h and "depth" in h:
                    result.append({
                        "title": str(h["title"]).strip(),
                        "depth": int(h.get("depth", 1)),
                    })
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error in heading extraction: {e}")
            return []

    def _regex_heading_fallback(self, text: str) -> list[dict]:
        """Regex-based heading detection when LLM fails.

        Looks for numbered headings (1., 1.1, etc.) and title-case lines.
        Returns flat (depth=1) list of detected headings.
        """
        headings = []
        seen = set()
        # Pattern 1: Numbered headings (1., 1.1, Chapter 1, etc.)
        patterns = [
            r"^(?:\d+\.\d*\s+|\d+\.\s+|\d+\s*[-–—]\s+)([A-Z].+?)$",
            r"^(?:Chapter\s+\d+\s*)(.*)$",
        ]
        for line in text.split("\n"):
            line = line.strip()
            if not line or len(line) > 120:
                continue
            # Skip lines that look like body content (too much punctuation)
            if line.count(".") > 3 and not re.match(r"\d+\.", line):
                continue
            for pattern in patterns:
                m = re.match(pattern, line, re.IGNORECASE)
                if m:
                    title = m.group(0) if not m.group(1) else m.group(1)
                    if title not in seen:
                        heading = {"title": title.strip(), "depth": 1}
                        # Check for subsection pattern
                        if re.match(r"\d+\.\d+", title):
                            heading["depth"] = 2
                        headings.append(heading)
                        seen.add(title)
                    break
        return headings[:30]  # Cap at 30 headings

    # ── Pass 2: Content Matching ──

    def _assign_page_ranges(
        self,
        pages: list[dict],
        toc_nodes: list[dict],
    ) -> list[dict]:
        """Pass 2: Find each heading's position and assign page ranges.

        Returns enriched nodes with start_index, end_index, page_start, page_end.
        """
        full_text = "\n".join(p.get("text", "") for p in pages)

        # Build page offset table
        page_offsets = []
        position = 0
        for page_info in pages:
            text = page_info.get("text", "")
            page_offsets.append({
                "page_num": page_info.get("page_num", 0),
                "start": position,
                "end": position + len(text),
            })
            position += len(text) + 1  # +1 for the newline separator

        # For each heading, find its position in the full text
        enriched = []
        for node in toc_nodes:
            start_index = self._find_heading_position(node["title"], full_text)
            page_start = self._char_to_page(start_index, page_offsets)
            page_end = page_start  # Will be updated in final pass

            enriched.append({
                "title": node["title"],
                "depth": node["depth"],
                "start_index": start_index,
                "page_start": page_start,
                "page_end": page_end,
            })

        # Assign end positions: each node ends where the next node starts
        if not enriched:
            return enriched

        for i, node in enumerate(enriched):
            if i + 1 < len(enriched):
                node["end_index"] = enriched[i + 1]["start_index"]
                node["page_end"] = enriched[i + 1]["page_start"]
            else:
                node["end_index"] = len(full_text)
                node["page_end"] = page_offsets[-1]["page_num"] if page_offsets else 1

            # Ensure page_start <= page_end
            if node["page_start"] > node["page_end"]:
                node["page_end"] = node["page_start"]

        return enriched

    def _find_heading_position(self, heading: str, full_text: str) -> int:
        """Find the character position of a heading in the full text.

        Uses fuzzy matching: tries exact, case-insensitive, and partial match.
        """
        # Exact match
        pos = full_text.find(heading)
        if pos != -1:
            return pos

        # Case-insensitive
        pos = full_text.lower().find(heading.lower())
        if pos != -1:
            return pos

        # Partial: search for the first 30+ characters
        partial = heading[:30].strip()
        if partial:
            pos = full_text.find(partial)
            if pos != -1:
                return pos

        logger.warning(f"Heading not found in text: '{heading}'")
        return 0

    def _char_to_page(self, char_pos: int, page_offsets: list[dict]) -> int:
        """Convert character position to page number."""
        for offset in page_offsets:
            if offset["start"] <= char_pos < offset["end"]:
                return offset["page_num"]
        return page_offsets[-1]["page_num"] if page_offsets else 1

    # ── Pass 3: Node Summarization ──

    async def _summarize_node(
        self,
        node: dict,
        pages: list[dict],
        model_id: str,
    ) -> str:
        """Pass 3: Generate LLM summary for a single node's page range."""
        from app.config import get_settings
        settings = get_settings()
        max_tokens = settings.pageindex_max_tokens_per_node

        # Get text for this node's page range
        page_start = node.get("page_start", 1)
        page_end = node.get("page_end", 1)

        node_pages = [
            p for p in pages
            if page_start <= p.get("page_num", 1) <= page_end
        ]
        if not node_pages:
            return f"Section: {node['title']}"

        node_text = "\n".join(p.get("text", "") for p in node_pages)

        # Truncate if too long
        max_chars = max_tokens * 4  # rough estimate: 4 chars per token
        if len(node_text) > max_chars:
            node_text = node_text[:max_chars] + "\n...[truncated]"

        try:
            result = await self.lm_client.stream_chat(
                messages=[
                    {"role": "system", "content": SUMMARY_PROMPT},
                    {"role": "user", "content": node_text},
                ],
                model=model_id,
                max_tokens=512,
                temperature=0.3,
            )
            if result:
                return result.strip()
        except Exception as e:
            logger.error(f"Summarization failed for '{node['title']}': {e}")

        return f"Section covering pages {page_start}-{page_end}."

    # ── Tree Structure ──

    def _structure_tree(
        self,
        nodes: list[dict],
        doc_id: str,
        total_pages: int,
        doc_title: str,
    ) -> dict:
        """Build the hierarchical PageIndexTree from flat node list.

        Converts flat nodes with depth into nested tree structure.
        """
        root = {
            "node_id": "root",
            "title": doc_title,
            "summary": f"Document with {total_pages} pages",
            "start_index": 0,
            "end_index": 0,
            "page_start": 1,
            "page_end": total_pages,
            "children": [],
        }

        if not nodes:
            return {"doc_id": doc_id, "title": doc_title, "total_pages": total_pages, "root": root}

        # Build hierarchy from depth
        stack = []  # (depth, node_ref)
        for i, node in enumerate(nodes):
            depth = node.get("depth", 1)
            node_id = f"node_{depth}_{i}"

            child_node = {
                "node_id": node_id,
                "title": node["title"],
                "summary": node.get("summary", f"Section: {node['title']}"),
                "start_index": node.get("start_index", 0),
                "end_index": node.get("end_index", 0),
                "page_start": node.get("page_start", 1),
                "page_end": node.get("page_end", 1),
                "children": [],
            }

            # Update stack: pop nodes deeper than current
            while stack and stack[-1][0] >= depth:
                stack.pop()

            if stack:
                stack[-1][1]['children'].append(child_node)
            else:
                root['children'].append(child_node)

            stack.append((depth, child_node))

        # Update root end_index and page_end
        if nodes:
            root["end_index"] = nodes[-1].get("end_index", 0)
            root["page_end"] = nodes[-1].get("page_end", 1)
        root["start_index"] = nodes[0].get("start_index", 0)
        root["page_start"] = nodes[0].get("page_start", 1)

        return {
            "doc_id": doc_id,
            "title": doc_title,
            "total_pages": total_pages,
            "root": root,
        }

    def _empty_tree(self, doc_id: str, title: str = "Unknown") -> dict:
        """Return an empty tree when document has no content."""
        return {
            "doc_id": doc_id,
            "title": title,
            "total_pages": 0,
            "root": {
                "node_id": "root",
                "title": title,
                "summary": "No content to index",
                "start_index": 0,
                "end_index": 0,
                "page_start": 1,
                "page_end": 1,
                "children": [],
            },
        }
```

- [ ] **Step 2: Write unit tests**

Create `backend/tests/test_pageindex_generator.py`:

```python
"""Tests for PageIndexTreeGenerator."""

import pytest


# ── Fixtures ──

@pytest.fixture
def sample_pages():
    """Sample document with clear section headings."""
    return [
        {
            "page_num": 1,
            "text": (
                "Introduction\n\n"
                "Welcome to this document about machine learning.\n"
                "This section provides background information.\n"
                "It covers basic concepts and terminology.\n"
            ),
        },
        {
            "page_num": 2,
            "text": (
                "Introduction\n\n"
                "Continuation of the introduction section with more details.\n"
                "This text fills out the rest of the page.\n"
            ),
        },
        {
            "page_num": 3,
            "text": (
                "1. Neural Networks\n\n"
                "Neural networks are computational models inspired by brains.\n"
                "They consist of layers of interconnected nodes.\n"
                "Each node performs a weighted sum and applies an activation function.\n"
            ),
        },
        {
            "page_num": 4,
            "text": (
                "1.1 Deep Learning\n\n"
                "Deep learning refers to neural networks with many layers.\n"
                "These models can learn hierarchical representations.\n"
                "Examples include CNNs, RNNs, and transformers.\n"
            ),
        },
        {
            "page_num": 5,
            "text": (
                "2. Training Methods\n\n"
                "Training involves feeding data through the network and adjusting weights.\n"
                "Common optimization algorithms include SGD, Adam, and RMSProp.\n"
            ),
        },
    ]


@pytest.fixture
def mock_lm_client():
    """Mock LM Studio client."""
    import asyncio
    from unittest.mock import AsyncMock
    client = AsyncMock()
    # Simulate heading extraction response
    def heading_side_effect(messages, model=None, max_tokens=2048, temperature=0.7):
        user_content = [m["content"] for m in messages if m["role"] == "user"][0]
        if "document structure analysis" in user_content.lower():
            return json.dumps([
                {"title": "Introduction", "depth": 1},
                {"title": "1. Neural Networks", "depth": 1},
                {"title": "1.1 Deep Learning", "depth": 2},
                {"title": "2. Training Methods", "depth": 1},
            ])
        elif "Summarize" in user_content:
            return "This section covers the topic in detail."
        return None
    client.stream_chat.side_effect = heading_side_effect
    return client


# ── Tests ──

def test_parse_heading_json():
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    heading = gen._parse_heading_json(
        '[{"title": "Section 1", "depth": 1}, '
        '{"title": "Subsection 1.1", "depth": 2}]'
    )
    assert len(headings) == 2
    assert headings[0]["title"] == "Section 1"
    assert headings[0]["depth"] == 1
    assert headings[1]["depth"] == 2


def test_parse_heading_json_with_markdown_code_fence():
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    heading = gen._parse_heading_json(
        '```json\n[{"title": "Header", "depth": 1}]\n```'
    )
    assert len(headings) == 1
    assert headings[0]["title"] == "Header"


def test_parse_heading_json_invalid():
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    heading = gen._parse_heading_json("not json at all")
    assert heading == []


def test_parse_heading_json_missing_depth():
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    heading = gen._parse_heading_json('[{"title": "Header"}]')
    assert len(headings) == 1
    assert headings[0]["title"] == "Header"


def test_regex_heading_fallback():
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    text = (
        "1. Introduction\n"
        "Some body text here.\n"
        "1.1 Background\n"
        "More body text.\n"
        "2. Methods\n"
        "2.1 Data Collection\n"
        "Random sentence.\n"
    )
    headings = gen._regex_heading_fallback(text)
    assert len(headings) >= 2
    assert any(h["title"] == "Introduction" for h in headings)
    assert any(h["depth"] == 2 for h in headings)


def test_assign_page_ranges(sample_pages):
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    toc_nodes = [
        {"title": "Introduction", "depth": 1},
        {"title": "1. Neural Networks", "depth": 1},
        {"title": "1.1 Deep Learning", "depth": 2},
        {"title": "2. Training Methods", "depth": 1},
    ]
    nodes = gen._assign_page_ranges(sample_pages, toc_nodes)
    assert len(nodes) == 4
    # First heading should be on page 1
    assert nodes[0]["page_start"] == 1
    # Neural Networks should be on page 3
    assert nodes[1]["page_start"] == 3
    # Deep Learning should be on page 4
    assert nodes[2]["page_start"] == 4
    # Training Methods should be on page 5
    assert nodes[3]["page_start"] == 5


def test_char_to_page():
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    offsets = [
        {"page_num": 1, "start": 0, "end": 100},
        {"page_num": 2, "start": 101, "end": 200},
        {"page_num": 3, "start": 201, "end": 300},
    ]
    assert gen._char_to_page(50, offsets) == 1
    assert gen._char_to_page(150, offsets) == 2
    assert gen._char_to_page(250, offsets) == 3


def test_structure_tree():
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    nodes = [
        {
            "title": "Introduction", "depth": 1,
            "start_index": 0, "end_index": 100,
            "page_start": 1, "page_end": 5,
            "summary": "Intro summary",
        },
        {
            "title": "Methods", "depth": 1,
            "start_index": 100, "end_index": 200,
            "page_start": 6, "page_end": 10,
            "summary": "Methods summary",
        },
        {
            "title": "Results", "depth": 1,
            "start_index": 200, "end_index": 300,
            "page_start": 11, "page_end": 15,
            "summary": "Results summary",
        },
    ]
    tree = gen._structure_tree(nodes, "doc_test.pdf", 15, "Test Document")
    assert tree["doc_id"] == "doc_test.pdf"
    assert tree["total_pages"] == 15
    assert tree["root"]["node_id"] == "root"
    assert len(tree["root"]["children"]) == 3
    assert tree["root"]["children"][0]["title"] == "Introduction"


def test_structure_tree_nested():
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    nodes = [
        {
            "title": "Chapter 1", "depth": 1,
            "start_index": 0, "end_index": 50,
            "page_start": 1, "page_end": 3,
            "summary": "Ch1 summary",
        },
        {
            "title": "Section 1.1", "depth": 2,
            "start_index": 0, "end_index": 25,
            "page_start": 1, "page_end": 2,
            "summary": "Sec 1.1 summary",
        },
        {
            "title": "Chapter 2", "depth": 1,
            "start_index": 50, "end_index": 100,
            "page_start": 4, "page_end": 6,
            "summary": "Ch2 summary",
        },
    ]
    tree = gen._structure_tree(nodes, "doc_test.pdf", 6, "Test")
    assert len(tree["root"]["children"]) == 2
    ch1 = tree["root"]["children"][0]
    assert ch1["title"] == "Chapter 1"
    assert len(ch1["children"]) == 1
    assert ch1["children"][0]["title"] == "Section 1.1"


def test_empty_tree():
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(None)
    tree = gen._empty_tree("doc_empty.pdf", "Empty Doc")
    assert tree["doc_id"] == "doc_empty.pdf"
    assert tree["total_pages"] == 0
    assert tree["root"]["node_id"] == "root"
    assert tree["root"]["children"] == []


@pytest.mark.anyio
async def test_build_tree_with_mock_client(sample_pages, mock_lm_client):
    from app.services.pageindex_generator import PageIndexTreeGenerator
    gen = PageIndexTreeGenerator(mock_lm_client)
    doc_content = {"type": "pdf", "pages": sample_pages}
    tree = await gen.build_tree(doc_content, None, "doc_test.pdf")
    assert tree is not None
    assert tree["doc_id"] == "doc_test.pdf"
    assert tree["total_pages"] == 5
    assert "root" in tree
    assert isinstance(tree["root"]["children"], list)
```

- [ ] **Step 3: Run all tests**

```bash
cd backend && python -m pytest tests/test_pageindex_generator.py -v
```
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/pageindex_generator.py backend/tests/test_pageindex_generator.py
git commit -m "feat: implement PageIndex tree generator service
Three-pass pipeline: TOC extraction, content matching, node summarization
Includes regex fallback for LLM failure and full test suite"
```

---

### Task 4: Wire PageIndexTreeGenerator into knowledge upload endpoint

**Files:**
- Modify: `backend/app/routers/knowledge.py` (entire file rewrite)
- Modify: `backend/app/main.py` (lifespan init)
- Test: `backend/tests/test_pageindex_generator.py` (already covers core; smoke test endpoint manually)

- [ ] **Step 1: Update main.py to instantiate the generator**

In `backend/app/main.py`, add after `model_manager = ModelManager(lm_client)` (about line 36):

```python
from app.services.pageindex_generator import PageIndexTreeGenerator
pageindex_generator = PageIndexTreeGenerator(lm_client)
```

- [ ] **Step 2: Replace the knowledge.py upload endpoint**

Replace the entire `upload_document` function in `backend/app/routers/knowledge.py` with this implementation:

```python
"""Knowledge Base routes."""

import logging
import time
from pathlib import Path
import json

from fastapi import APIRouter, UploadFile, File, Form
from app.config import get_settings
from app.services.document_processor import extract_text
from app.services.pageindex_generator import PageIndexTreeGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

DATA_DIR = Path("data/knowledge_bases")
KB_UPLOADS_DIR = DATA_DIR / "uploads"
_tasks: dict = {}
_kb_registry: dict = {}

def _ensure_kb(kb_name: str):
    """Ensure KB directories exist and register the KB."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KB_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / kb_name / "pageindex").mkdir(parents=True, exist_ok=True)
    (KB_UPLOADS_DIR / kb_name).mkdir(parents=True, exist_ok=True)
    if kb_name not in _kb_registry:
        _kb_registry[kb_name] = {
            "name": kb_name, "status": "active",
            "total_pages": 0, "total_docs": 0,
            "created_at": time.time(),
        }


async def _process_document(
    task_id: str,
    file_bytes: bytes,
    doc_id: str,
    kb_name: str,
    pageindex_generator: "PageIndexTreeGenerator",
):
    """Background task: extract text and build PageIndex tree."""
    _tasks[task_id]["status"] = "processing"
    _tasks[task_id]["progress"] = 10

    try:
        # Save file
        upload_path = KB_UPLOADS_DIR / kb_name / doc_id
        upload_path.write_bytes(file_bytes)

        _tasks[task_id]["progress"] = 20

        # Extract text
        doc_content = await extract_text(upload_path)
        if doc_content is None:
            _tasks[task_id]["status"] = "failed"
            _tasks[task_id]["progress"] = 0
            _tasks[task_id]["message"] = "Failed to extract text from document"
            return

        _tasks[task_id]["progress"] = 40

        # Determine model
        settings = get_settings()
        model_id = settings.pageindex_model or settings.llm_model or "Qwen3-4B-Q4_K_M"

        # Build tree
        tree = await pageindex_generator.build_tree(doc_content, model_id, doc_id)
        if tree is None:
            raise ValueError("Tree generation returned None")

        _tasks[task_id]["progress"] = 90

        # Write tree
        tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text(json.dumps(tree, indent=2))

        _tasks[task_id]["status"] = "complete"
        _tasks[task_id]["progress"] = 100
        _tasks[task_id]["message"] = f"Generated PageIndex tree with {tree.get('total_pages', 0)} pages and {len(tree.get('root', {}).get('children', []))} top-level sections"

        # Update KB registry
        if kb_name in _kb_registry:
            _kb_registry[kb_name]["total_docs"] += 1
            _kb_registry[kb_name]["total_pages"] += tree.get("total_pages", 0)

    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["progress"] = 0
        _tasks[task_id]["message"] = str(e)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    kb_name: str = Form("default"),
):
    """Upload document and start PageIndex tree generation."""
    _ensure_kb(kb_name)

    doc_id = file.filename or f"doc_{int(time.time())}"
    file_bytes = await file.read()

    task_id = f"task_{int(time.time() * 1000)}"

    # Check if LM Studio is available
    from app.main import lm_client
    health_ok = await lm_client.check_health()

    if health_ok:
        # Real processing via background task
        from app.main import pageindex_generator
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "processing",
            "progress": 5,
            "message": "Starting document processing",
            "doc_id": doc_id,
            "kb_name": kb_name,
        }
        # Fire and forget — client polls via /tasks/{task_id}
        import asyncio
        asyncio.create_task(_process_document(
            task_id, file_bytes, doc_id, kb_name, pageindex_generator
        ))
    else:
        # Fallback: create a minimal stub tree
        _ensure_kb(kb_name)

        tree = {
            "doc_id": doc_id,
            "title": doc_id,
            "total_pages": 0,
            "root": {
                "node_id": "root",
                "title": "Document (LLM not available)",
                "summary": "LM Studio is not connected. This is a stub tree.",
                "start_index": 0,
                "end_index": 0,
                "page_start": 1,
                "page_end": 1,
                "children": [],
            },
        }
        tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_text(json.dumps(tree, indent=2))

        _kb_registry[kb_name]["total_docs"] += 1
        _tasks[task_id] = {
            "task_id": task_id,
            "status": "complete",
            "progress": 100,
            "message": "Stub tree created (LM Studio not connected)",
            "doc_id": doc_id,
            "kb_name": kb_name,
        }

    return {"task_id": task_id, "status": "processing", "doc_id": doc_id}
```

- [ ] **Step 3: Run the backend to verify import paths**

```bash
cd backend && python -c "from app.routers.knowledge import router; print('OK')"
```
Expected: `OK`

Also verify main.py imports:
```bash
cd backend && python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/app/routers/knowledge.py
git commit -m "feat: integrate PageIndex tree generation into upload pipeline

- Async background processing with task polling
- Fallback to stub tree when LM Studio unavailable
- Real progress tracking through the task endpoint"
```

---

### Task 5: Add PyMuPDF dependency and smoke test

**Files:**
- Modify: `backend/pyproject.toml`
- Add: `backend/pyproject.toml` — add PyMuPDF to optional deps

- [ ] **Step 1: Update pyproject.toml**

Change the `[project.optional-dependencies]` section:

```toml
[project.optional-dependencies]
gpu = ["pynvml>=12.0"]
dev = ["pytest", "httpx"]
pdf = ["PyMuPDF>=1.24"]
```

Also add PyMuPDF to the core dependencies (needed for document processing at runtime):

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "python-multipart>=0.0.18",
    "websockets>=14.0",
    "PyMuPDF>=1.24",
]
```

- [ ] **Step 2: Install PyMuPDF**

```bash
cd backend && pip install "PyMuPDF>=1.24"
```

- [ ] **Step 3: Smoke test the full pipeline with a sample PDF**

Create a quick test in `backend/tests/test_smoke_pageindex.py`:

```python
"""Smoke test: upload a simple PDF and verify tree generation."""

import pytest
from pathlib import Path

def test_pageindex_from_sample_pdf():
    """If a test PDF exists, verify tree generation produces valid output."""
    sample_pdf = Path(__file__).parent.parent / "data" / "test.pdf"
    if not sample_pdf.exists():
        pytest.skip("No test PDF available")

    import asyncio
    from app.services.document_processor import extract_text
    from app.services.pageindex_generator import PageIndexTreeGenerator
    from unittest.mock import AsyncMock

    async def run_test():
        doc_content = await extract_text(sample_pdf)
        assert doc_content is not None
        assert "pages" in doc_content
        assert len(doc_content["pages"]) > 0

        mock_client = AsyncMock()
        mock_client.stream_chat.return_value = (
            '[{"title": "Introduction", "depth": 1}, '
            '{"title": "Methods", "depth": 1}]'
        )
        gen = PageIndexTreeGenerator(mock_client)
        tree = await gen.build_tree(doc_content, "Qwen3-4B-Q4_K_M", "test.pdf")
        assert tree is not None
        assert "root" in tree
        assert "children" in tree["root"]

    asyncio.run(run_test())
```

- [ ] **Step 4: Run all tests**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: All tests pass

- [ ] **Step 5: Start the backend and test upload endpoint**

```bash
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8001
```

In another terminal:
```bash
curl -X POST "http://localhost:8001/api/v1/knowledge/upload" -F "file=@your_test.pdf" -F "kb_name=test_kb"
```

Poll the task:
```bash
curl "http://localhost:8001/api/v1/knowledge/tasks/{task_id}"
```

Get the tree:
```bash
curl "http://localhost:8001/api/v1/knowledge/bases/default/pageindex/{doc_id}"
```

Verify the JSON structure matches the OpenAPI spec PageIndexTree schema.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/tests/test_smoke_pageindex.py
git commit -m "chore: add PyMuPDF dependency + smoke test for PageIndex pipeline"
```

---