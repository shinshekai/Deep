# PageIndex Tree Generation — Design Spec

**Date:** 2026-04-06
**Status:** Draft — For Review

## Overview

PageIdex tree generation converts uploaded PDF/TXT/MD documents into hierarchical JSON tree indexes with LLM-reasoned section identification and summaries. This is the core differentiator of UDIP — reasoning-based hierarchical document indexing instead of vector-only chunking.

## Architecture

### Three-Pass Pipeline

```
Document → extract_text() → Pass 1: TOC Extract → Pass 2: Content Match → Pass 3: Summarize → Write JSON
```

**Pass 1 (TOC Extraction):** Concatenate the first 20 pages of the document, identify numbered headings, all-caps section titles, and hierarchy patterns. Send to LLM (T2 model: Qwen3-4B or -8B) with structured prompt to output JSON array of section headings with titles and nesting depth.

**Pass 2 (Content Match):** For each extracted heading, scan the full document text to find exact character positions. Assign page_start, page_end, start_index, and end_index to each node. Pages are assigned to the closest preceding heading.

**Pass 3 (Node Summarization):** For each top-level node, extract the text from its page range and send to LLM with prompt to generate 2-3 sentence summary. This becomes the node's summary field.

**Output:** PageIndexTree JSON per OpenAPI spec:
```json
{
  "doc_id": "doc_filename.pdf",
  "title": "Document Title",
  "total_pages": 42,
  "root": {
    "node_id": "root",
    "title": "Document Title",
    "summary": "3-5 sentence overview",
    "start_index": 0,
    "end_index": 123456,
    "page_start": 1,
    "page_end": 42,
    "children": [
      {
        "node_id": "node_1_0",
        "title": "Section 1: Introduction",
        "summary": "LLM-generated summary",
        "start_index": 0,
        "end_index": 15000,
        "page_start": 1,
        "page_end": 5,
        "children": [
          {
            "node_id": "node_2_0",
            "title": "Subsection 1.1",
            "summary": "...",
            "start_index": 0,
            "end_index": 5000,
            "page_start": 1,
            "page_end": 3,
            "children": []
          }
        ]
      }
    ]
  }
}
```

### Component Design

**New file:** `backend/app/services/pageindex_generator.py` (~300 lines)

```python
class PageIndexTreeGenerator:
    def __init__(self, lm_client):
        self.lm_client = lm_client

    async def build_tree(self, doc_content, model_id) -> dict:
        """Main entry point. doc_content from document_processor.extract_text()"""
        # ── Pass 1: TOC Extraction ──
        toc_text = self._extract_toc_candidates(doc_content)
        toc_nodes = await self._identify_headings(toc_text, model_id)

        # ── Pass 2: Content Matching ──
        nodes_with_ranges = self._assign_page_ranges(doc_content["pages"], toc_nodes)

        # ── Pass 3: Node Summarization ──
        for node in nodes_with_ranges:
            node["summary"] = await self._summarize_node(node, doc_content, model_id)

        return self._structure_tree(nodes_with_ranges)
```

**Pass 1 — `_identify_headings(toc_text, model_id)`:**
- Prompt: "Analyze this document text and extract section headings and their hierarchy as JSON array with `title` and `depth` for each."
- Returns: `[{"title": "1. Introduction", "depth": 1}, {"title": "1.1 Background", "depth": 2}]`

**Pass 2 — `_assign_page_ranges(pages, toc_nodes)`:**
- For each heading, search document text for the heading title
- Record character position, convert to page numbers
- Handles heading not found: assigns to previous node's range

**Pass 3 — `_summarize_node(node, doc_content, model_id)`:**
- Extract text from node's page range
- If more than PAGEINDEX_MAX_TOKENS_PER_NODE (20000), truncate to first N pages
- Prompt: "Summarize this document section in 2-3 sentences. Focus on key points."
- Returns summary string

### Integration with Knowledge Upload

The upload endpoint in `knowledge.py` currently returns an immediate stub. Replace with:

1. Save uploaded file to `data/knowledge_bases/{kb_name}/uploads/{doc_id}`
2. Call `extract_text()` → get pages
3. Call `PageIndexTreeGenerator.build_tree()` → get tree
4. Write tree JSON to `data/knowledge_bases/{kb_name}/pageindex/{doc_id}.json`
5. For documents >50 pages: run asynchronously, return `task_id` for polling
6. Existing `/api/v1/knowledge/tasks/{task_id}` endpoint reused for status polling

### Error Handling & Fallbacks

| Failure | Response |
|---------|----------|
| LLM unavailable | Return `{"title": "Document", "summary": "LLM not available", "children": []}` with warning log |
| No headings found | Create single root node covering all pages |
| Document >200 pages | Split into batches of 100 pages, generate sub-trees, merge under root |
| Character position lookup fails | Use page numbers only, set `start_index=0`, `end_index=-1` |
| LLM response parsing error | Retry once, then use regex heading fallback |

### Performance Targets

- PageIndex tree generation: < 60s for 100-page document (NFR-1.1)
- Tree storage: < 1 MB per 100 pages (NFR-2.4)
- Model: T2 (Qwen3-4B or -8B) — default, configurable via PAGEINDEX_MODEL
- Max pages per node: 10 (PAGEINDEX_MAX_PAGES_PER_NODE)
- Max tokens per node: 20000 (PAGEINDEX_MAX_TOKENS_PER_NODE)

### Data Storage Layout

Tree JSON files written to:
`data/knowledge_bases/{kb_name}/pageindex/{doc_id}.json`

### Environment Variables Used

- `PAGEINDEX_MODEL` — Override LLM model for tree gen (defaults to LLM_MODEL)
- `PAGEINDEX_MAX_PAGES_PER_NODE` — Max pages per tree node (default: 10)
- `PAGEINDEX_MAX_TOKENS_PER_NODE` — Max tokens per node (default: 20000)

Note: These are NOT in config.py yet — need to add them.

### Files to Create/Modify

1. **CREATE** `backend/app/services/pageindex_generator.py` — Main service (~300 lines)
2. **MODIFY** `backend/app/routers/knowledge.py` — Replace stub upload with real pipeline
3. **MODIFY** `backend/app/config.py` — Add PAGEINDEX_* settings
4. **MODIFY** `backend/app/main.py` — Wire PageIndexTreeGenerator into lifespan

## Alternatives Considered

- **Single-prompt approach:** One LLM call for entire document. Rejected — token limit issues for docs >50 pages.
- **Regex + LLM hybrid:** Use regex for heading detection, LLM for summaries. Rejected — doesn't work for PDFs without heading markup.
