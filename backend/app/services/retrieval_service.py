"""Retrieval service: pipeline dispatch and helpers."""

import json
import logging
import time
from pathlib import Path

from pydantic import BaseModel

from app.services.telemetry import add_event, trace_span

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_bases"


class RetrieveRequest(BaseModel):
    query: str
    kb_name: str
    doc_id: str | None = None
    retrieval_pipeline: str = "tree"
    top_k: int = 5
    min_score: float = 0.3


from app.services.security import safe_doc_id as _safe_doc_id
from app.services.security import safe_name as _safe_name


def _load_pageindex_tree(kb_name: str, doc_id: str) -> dict | None:
    safe_kb = _safe_name(kb_name, default="default")
    safe_doc = _safe_doc_id(doc_id, default="doc")
    tree_path = DATA_DIR / safe_kb / "pageindex" / f"{safe_doc}.json"
    if tree_path.exists():
        return json.loads(tree_path.read_text())
    return None


def _list_pageindex_docs(kb_name: str) -> list[str]:
    safe_kb = _safe_name(kb_name, default="default")
    tree_dir = DATA_DIR / safe_kb / "pageindex"
    if not tree_dir.exists():
        return []
    return [f.stem for f in tree_dir.glob("*.json")]


def _get_tree_search():
    from app import state
    from app.services.tree_search import TreeSearch

    return TreeSearch(lm_client=state.lm_client)


def _get_vector_kb():
    from app import state
    from app.services.vector_kb import VectorKBService

    return VectorKBService(DATA_DIR, lm_client=state.lm_client)


async def retrieve(req: RetrieveRequest):
    """Execute retrieval using tree/hybrid/naive/combined pipelines."""
    start = time.time()

    req.kb_name = _safe_name(req.kb_name, default="default")
    if req.doc_id:
        req.doc_id = _safe_doc_id(req.doc_id, default="doc")

    with trace_span(
        "retrieval.execute",
        {"kb": req.kb_name, "pipeline_requested": req.retrieval_pipeline, "top_k": req.top_k},
    ):
        from app.services.complexity_scorer import score_query_complexity
        from app.services.query_router import RouteContext, route_query

        tree_docs = _list_pageindex_docs(req.kb_name)
        has_trees = len(tree_docs) > 0
        has_vectors = (DATA_DIR / req.kb_name / "vectors").exists()

        complexity, _ = score_query_complexity(req.query, doc_pages=len(tree_docs))

        pipeline = route_query(
            query=req.query,
            kb_name=req.kb_name,
            doc_id=req.doc_id,
            retrieval_pipeline=req.retrieval_pipeline,
            context=RouteContext(
                has_trees=has_trees, has_vectors=has_vectors, complexity=complexity
            ),
        )
        add_event(
            "pipeline_selected",
            {"pipeline": pipeline, "has_trees": has_trees, "has_vectors": has_vectors},
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
            k = 60
            rrf_scores: dict[tuple, tuple[float, dict]] = {}
            for rank, r in enumerate(tree_results):
                key = (r.get("doc_id", ""), r.get("section", ""), r.get("page", 0))
                rrf = 1.0 / (k + rank + 1)
                if key in rrf_scores:
                    rrf_scores[key] = (rrf_scores[key][0] + rrf, r)
                else:
                    rrf_scores[key] = (rrf, r)
            for rank, r in enumerate(vector_results):
                key = (r.get("doc_id", ""), r.get("section", ""), r.get("page", 0))
                rrf = 1.0 / (k + rank + 1)
                if key in rrf_scores:
                    rrf_scores[key] = (rrf_scores[key][0] + rrf, r)
                else:
                    rrf_scores[key] = (rrf, r)
            merged = []
            for _key, (rrf_score, r) in rrf_scores.items():
                entry = dict(r)
                entry["rrf_score"] = round(rrf_score, 4)
                entry["relevance_score"] = round(rrf_score, 4)
                merged.append(entry)
            merged.sort(key=lambda r: r.get("rrf_score", 0), reverse=True)
            results = merged[: req.top_k]
        elif pipeline == "ara":
            from app import state
            from app.services.ara_compiler import ARACompiler

            ara_compiler = ARACompiler(state.lm_client)

            ara_dir = DATA_DIR / req.kb_name / "ara"
            if ara_dir.exists():
                for doc_path in ara_dir.iterdir():
                    if not doc_path.is_dir():
                        continue
                    doc_id = doc_path.name
                    if req.doc_id and doc_id != req.doc_id:
                        continue

                    artifact = ara_compiler.load(DATA_DIR / req.kb_name, doc_id)
                    if not artifact:
                        continue

                    claims = ara_compiler.search_claims(artifact, req.query)
                    for c in claims:
                        results.append(
                            {
                                "doc_id": doc_id,
                                "title": artifact.title,
                                "type": "claim",
                                "content": c.statement,
                                "relevance_score": 0.8,
                                "metadata": {"claim_id": c.claim_id, "provenance": c.provenance},
                            }
                        )

                    heuristics = ara_compiler.search_heuristics(artifact, req.query)
                    for h in heuristics:
                        results.append(
                            {
                                "doc_id": doc_id,
                                "title": artifact.title,
                                "type": "heuristic",
                                "content": f"{h.description}\nRationale: {h.rationale}",
                                "relevance_score": 0.8,
                                "metadata": {
                                    "heuristic_id": h.heuristic_id,
                                    "constraints": h.constraints,
                                },
                            }
                        )

            results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            results = results[: req.top_k]

        elapsed = (time.time() - start) * 1000
        add_event(
            "retrieval_complete", {"result_count": len(results), "latency_ms": round(elapsed, 1)}
        )

        return {
            "query": req.query,
            "pipeline_used": pipeline,
            "results": results,
            "retrieval_latency_ms": round(elapsed, 1),
            "model_tier_used": 2,
            "total_candidates_scored": total_candidates,
        }
