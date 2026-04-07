"""Retrieval routes: POST /retrieve, POST /query, DELETE document."""

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


class QueryRequest(BaseModel):
    query: str
    kb_name: str
    mode: str = "auto"
    retrieval_pipeline: str = "tree"
    session_id: str = ""
    doc_id: str | None = None


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
    from app.main import lm_client
    return TreeSearch(lm_client=lm_client)


def _get_vector_kb():
    from app.services.vector_kb import VectorKBService
    return VectorKBService(DATA_DIR)


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
        results = vector_kb.naive_search(
            query=req.query,
            kb_name=req.kb_name,
            top_k=req.top_k,
            min_score=req.min_score,
        )
    elif pipeline == "hybrid":
        vector_kb = _get_vector_kb()
        results = vector_kb.hybrid_search(
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
        vector_results = vector_kb.naive_search(
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


# ── POST /query ──

@router.post("/query")
async def query_http(req: QueryRequest):
    """Non-streaming HTTP Q&A. Uses TreeSearch for context + LLM for answers."""
    start = time.time()

    from app.services.complexity_scorer import score_query_complexity
    from app.main import lm_client

    # Set session_id if not provided
    session_id = req.session_id or f"solve_{int(time.time())}"
    solve_dir = f"data/user/solve/{session_id}"
    agent_steps = []

    # Step 1: Retrieve relevant context via TreeSearch
    tree_search = _get_tree_search()
    retrieve_results = await tree_search.search(
        query=req.query,
        kb_name=req.kb_name,
        doc_id=req.doc_id,
        top_k=5,
        min_score=0.3,
    )
    context = "\n\n".join(
        f"[{r.get('section', '')}] (doc:{r.get('doc_id', '')}, p.{r.get('page', '')}): "
        f"{r.get('summary', '')}"
        for r in retrieve_results
    )

    agent_steps.append({
        "agent": "retrieve",
        "content": f"Found {len(retrieve_results)} relevant sections",
        "timestamp": time.time(),
    })

    # Step 2: Compute complexity, determine tier
    score, tier = score_query_complexity(
        query_text=req.query,
        retrieved_chunks=len(retrieve_results),
        doc_pages=0,
    )

    agent_steps.append({
        "agent": "route",
        "content": f"Complexity: {score:.2f} -> Tier {tier}",
        "timestamp": time.time(),
    })

    # Step 3: Generate answer
    context_section = f"\n\nContext from documents:\n{context}" if context else ""
    answer_content = ""
    citations = []

    health_ok = await lm_client.check_health()

    if health_ok:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert document intelligence assistant. "
                    "Provide thorough, well-structured answers based on the "
                    "provided context. If the context doesn't contain enough "
                    "information, say so clearly."
                ),
            },
            {
                "role": "user",
                "content": f"{req.query}{context_section}",
            },
        ]

        answer_content = await lm_client.stream_chat(
            messages=messages,
            max_tokens=4096,
        ) or "No response generated."

        agent_steps.append({
            "agent": "solve",
            "content": answer_content[:300],
            "timestamp": time.time(),
        })

        # Build citations from retrieval results
        for r in retrieve_results:
            citations.append({
                "doc_id": r["doc_id"],
                "page": r["page"],
                "section": r["section"],
                "node_id": r.get("node_id", ""),
            })
    else:
        answer_content = (
            f"LM Studio is not available. Your query was: {req.query}\n\n"
            f"Retrieved {len(retrieve_results)} document sections for context.\n"
            f"Connect LM Studio to get AI-generated answers."
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
