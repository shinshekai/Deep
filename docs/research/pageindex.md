# Research Foundations: PageIndex (VectifyAI)

## Core Thesis

**Similarity ≠ Relevance.** Vector-based RAG retrieves semantically *similar* text; PageIndex retrieves *relevant* text by reasoning over document structure. Inspired by AlphaGo's tree search.

## Architecture

### Phase 1: Tree Index Construction
```
PDF → page extraction → token counting → TOC detection → TOC extraction
→ Physical index mapping → Verification & auto-repair → Recursive node splitting
→ Summary generation → Document description
```

### Phase 2: Agentic Retrieval
Three tool functions exposed to LLM agent:
| Tool | Returns |
|------|---------|
| `get_document()` | Metadata: name, description, page count, status |
| `get_document_structure()` | Full tree JSON (text fields stripped) |
| `get_page_content(pages="5-7")` | Raw page text for specific page ranges |

**Retrieval is entirely agentic** — LLM decides which tools to call based on reasoning over tree structure.

## Key Decisions

1. **In-context index** — tree lives in LLM's context window, not external DB
2. **No embedding model** — only ML component is the LLM itself
3. **LiteLLM integration** — supports any provider without code changes
4. **Verification-as-invariant** — every TOC generation pass verified with bounded retries
5. **Zero chunking** — preserves semantic integrity via natural document sections

## Comparison: Vector RAG vs PageIndex

| Dimension | Vector RAG | PageIndex |
|-----------|-----------|-----------|
| Index | Embedding vectors in external DB | JSON tree in LLM context window |
| Granularity | Fixed chunks | Natural document sections |
| Retrieval signal | Cosine similarity | LLM reasoning + tree traversal |
| Cross-references | Missed | Followed via tree navigation |
| Explainability | Opaque vector matches | Traceable section visits |

## Relevance to Our Project

| PageIndex Pattern | Our Implementation | Gap |
|-------------------|-------------------|-----|
| Agentic retrieval | tree_search.py (LLM scores nodes) | PARTIAL |
| Verification-as-invariant | No verification passes | MISSING |
| Tree-based document structure | IndexNode type exists, no visualization | PARTIAL |
| Zero chunking | We use chunk-based FTS5 | DIFFERENT APPROACH |
