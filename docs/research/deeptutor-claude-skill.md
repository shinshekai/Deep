# Research Foundations: DeepTutor Claude Skill

## Architecture

```
SKILL.md              # Skill definition (triggers, workflows, prompts)
scripts/
├── kb_manager.py     # KB CRUD
├── graph_builder.py  # NetworkX graph ops
└── graph_retriever.py # Hybrid retrieval (BM25 + graph expansion)
kb/                   # Runtime KB storage
```

## Core Pattern: Declarative Skill + Thin Python Tools

| Concern | Handler | Why |
|---------|---------|-----|
| PDF reading, reasoning, tutoring | Claude (LLM) | Native reasoning capabilities |
| Graph storage, BM25, traversal | 3 Python scripts | Deterministic I/O |
| Workflow orchestration | SKILL.md | Declarative skill definition |

Total footprint: ~27KB, 1 pip dependency (networkx). Claims ~70% of original DeepTutor's value.

## 6 Workflows

1. **Initialize KB** — Extract text → chunk → build knowledge graph → store with NetworkX
2. **Dual-Loop Solve** (signature pattern):
   - Analysis Loop: Iterative retrieval (3-5 rounds) with 5 decision rules
   - Solve Loop: Plan solution chain → execute with citations → compile answer
3. **Generate Questions** — KB-grounded quiz with difficulty calibration
4. **Deep Research** — Multi-section academic report
5. **Guided Learning** — Prerequisite-aware teaching via graph traversal
6. **KB Management** — CRUD operations

## Knowledge Graph

- **Entity types**: concept, definition, theorem, formula, method, person, term
- **Relationship types**: defines, uses, extends, contradicts, part_of, prerequisite, derives_from, applies_to, related_to
- **Hybrid retrieval**: `score = α × BM25 + (1-α) × graph_boost` (α=0.7)

## Key Patterns

1. **No embeddings** — BM25 + graph traversal instead of vector similarity
2. **JSON as interchange format** — LLM outputs structured JSON → piped to scripts
3. **Prompt-as-architecture** — Entire methodology lives in SKILL.md
4. **Incremental graph building** — Entities merged, relation weights accumulate
5. **Citation-driven answering** — Every claim must reference source pages

## Relevance to Our Project

| DeepTutor Skill Pattern | Our Implementation | Gap |
|------------------------|-------------------|-----|
| Thin tool layer (3 scripts) | backend/ services (heavier) | DIFFERENT APPROACH |
| Hybrid retrieval (BM25 + graph) | FTS5 + vector (no graph) | PARTIAL |
| Citation-driven answering | Citations stored but not enforced | PARTIAL |
| Prompt-as-architecture | Prompt registry (YAML, not workflow-based) | PARTIAL |
