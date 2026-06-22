# deep-memory

Self-synthesizing local-first memory system for AI agents.

## Features
- **SQLite + FTS5** — Full-text search with porter unicode61 tokenizer
- **Device-scoped** — UUID v4 device_id isolation, no cross-device leakage
- **Progressive crystallization** — staged_observations → facts → user_l3 profiles
- **LLM-driven consolidation** — update/audit/dedup/merge modes
- **Dead-end prevention** — ARA-style exploration DAG with failure tracking
- **Provenance audit** — Full lineage tracking with integrity verification

## Installation
```bash
pip install deep-memory
```

## Usage
```python
from deep_memory import MemoryService

memory = MemoryService(db_path="data/memory.db")
await memory.initialize()

# Store and recall
await memory.store_episode(device_id="...", query="...", answer="...")
episodes = await memory.recall_episodes(device_id="...", query="...")

# Fact management
await memory.store_fact(device_id="...", content="...", source_type="solve")
facts = await memory.recall_facts(device_id="...", query="...")

# Dead-end prevention
dead_end_id = await memory.store_dead_end(device_id="...", title="...", ...)
preventions = await memory.get_dead_end_preventions(device_id="...", query="...")
```
