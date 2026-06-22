"""Multi-engine retrieval registry with per-KB binding.

Each knowledge base can specify its preferred retrieval engine.
Available engines: tree (PageIndex), vector (naive), hybrid (RRF),
combined (tree+vector), ara (exploration), graph (knowledge graph).
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ENGINES = ["tree", "vector", "hybrid", "combined", "ara", "graph"]
DEFAULT_ENGINE = "hybrid"


def get_kb_engine_preference(kb_name: str) -> str:
    """Read a KB's preferred retrieval engine from its metadata.

    Priority: metadata file → KB contents heuristics → default.
    """
    meta_file = Path("data/knowledge_bases") / kb_name / "kb_meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text())
            engine = meta.get("engine", "")
            if engine in ENGINES:
                return engine
        except (json.JSONDecodeError, OSError):
            pass

    pi_dir = Path("data/knowledge_bases") / kb_name / "pageindex"
    vec_dir = Path("data/knowledge_bases") / kb_name / "vectors"
    has_trees = pi_dir.exists() and any(pi_dir.glob("*.json"))
    has_vectors = vec_dir.exists() and any(vec_dir.glob("*.json"))

    if has_trees and not has_vectors:
        return "tree"
    if has_vectors and not has_trees:
        return "vector"
    return DEFAULT_ENGINE


def set_kb_engine_preference(kb_name: str, engine: str) -> None:
    """Set a KB's preferred retrieval engine."""
    if engine not in ENGINES:
        raise ValueError(f"Unknown engine: {engine}. Valid: {ENGINES}")

    meta_file = Path("data/knowledge_bases") / kb_name / "kb_meta.json"
    meta_file.parent.mkdir(parents=True, exist_ok=True)

    meta = {}
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    meta["engine"] = engine
    meta_file.write_text(json.dumps(meta, indent=2))
    logger.info("KB '%s' engine set to: %s", kb_name, engine)


def get_engine_description(engine: str) -> str:
    """Human-readable description of each engine."""
    descriptions = {
        "tree": "PageIndex tree-based — reasoning over document structure, best for structured docs",
        "vector": "Naive vector search — embedding similarity, best for semantic queries",
        "hybrid": "RRF merge of tree + vector — balanced coverage, default engine",
        "combined": "Tree + vector + RRF — comprehensive with ranking fusion",
        "ara": "ARA exploration pipeline — multi-agent research, best for complex multi-hop queries",
        "graph": "Knowledge graph traversal — entity-relationship reasoning",
    }
    return descriptions.get(engine, "Unknown engine")
