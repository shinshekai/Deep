"""Retrieval routes: POST /retrieve."""

import time
import json
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["retrieval"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases"


# ── Request/Response Schemas ──

class RetrieveRequest(BaseModel):
    query: str
    kb_name: str
    doc_id: str | None = None
    retrieval_pipeline: str = "tree"
    top_k: int = 5
    min_score: float = 0.3


# ── Helpers ──

def _load_pageindex_tree(kb_name: str, doc_id: str) -> dict | None:
    tree_path = DATA_DIR / kb_name / "pageindex" / f"{doc_id}.json"
    if tree_path.exists():
        return json.loads(tree_path.read_text())
    return None


def _list_pageindex_docs(kb_name: str) -> list[str]:
    tree_dir = DATA_DIR / kb_name / "pageindex"
    if not tree_dir.exists():
        return []
    return [f.stem for f in tree_dir.glob("*.json")]


def _get_tree_search():
    from app.services.tree_search import TreeSearch
    from app import state
    return TreeSearch(lm_client=state.lm_client)


def _get_vector_kb():
    from app.services.vector_kb import VectorKBService
    from app import state
    return VectorKBService(DATA_DIR, lm_client=state.lm_client)


# ── POST /retrieve ──

@router.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    """Execute retrieval using tree/hybrid/naive/combined pipelines."""
    start = time.time()

    from app.services.query_router import RouteContext, route_query

    # Determine pipeline
    tree_docs = _list_pageindex_docs(req.kb_name)
    has_trees = len(tree_docs) > 0
    has_vectors = (DATA_DIR / req.kb_name / "vectors").exists()

    pipeline = route_query(
        query=req.query,
        kb_name=req.kb_name,
        doc_id=req.doc_id,
        retrieval_pipeline=req.retrieval_pipeline,
        context=RouteContext(has_trees=has_trees, has_vectors=has_vectors),
    )

    results = []
    total_candidates = 0
    tree_search = None
    vector_kb = None

    if pipeline == "tree":
        tree_search = _get_tree_search()
        results = await tree_search.search(
            query=req.query,
            kb_name=req.kb_name,
            doc_id=req.doc_id,
            top_k=req.top_k,
            min_score=req.min_score,
        )
        total_candidates = len(tree_docs)
    elif pipeline == "naive":
        vector_kb = _get_vector_kb()
        results = await vector_kb.naive_search(
            query=req.query,
            kb_name=req.kb_name,
            top_k=req.top_k,
            min_score=req.min_score,
        )
    elif pipeline == "hybrid":
        vector_kb = _get_vector_kb()
        results = await vector_kb.hybrid_search(
            query=req.query,
            kb_name=req.kb_name,
            top_k=req.top_k,
            min_score=req.min_score,
        )
    elif pipeline == "combined":
        tree_search = _get_tree_search()
        vector_kb = _get_vector_kb()

        tree_results = await tree_search.search(
            query=req.query,
            kb_name=req.kb_name,
            doc_id=req.doc_id,
            top_k=req.top_k,
            min_score=req.min_score,
        )
        vector_results = await vector_kb.naive_search(
            query=req.query,
            kb_name=req.kb_name,
            top_k=req.top_k,
            min_score=req.min_score,
        )
        # Merge: tree results have higher weight, deduplicate by key
        seen = set()
        for r in tree_results + vector_results:
            key = (r.get("doc_id", ""), r.get("section", ""), r.get("page", 0))
            if key not in seen:
                seen.add(key)
                results.append(r)
        results = results[:req.top_k]
        total_candidates = len(tree_docs)

    elapsed = (time.time() - start) * 1000

    return {
        "query": req.query,
        "pipeline_used": pipeline,
        "results": results,
        "retrieval_latency_ms": round(elapsed, 1),
        "model_tier_used": 2,
        "total_candidates_scored": total_candidates,
    }
