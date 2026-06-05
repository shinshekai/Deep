"""HTTP query endpoint (non-streaming Q&A fallback for WebSocket /solve).

Implements POST /api/v1/query with:
- Same retrieval pipelines as WebSocket (tree/hybrid/naive/combined)
- Complexity scoring and model tier selection
- Synchronous LLM call (non-streaming to client)
- Structured response with citations and metadata
"""

import asyncio
import time
import logging
from typing import Optional, Literal
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

from app import state
from app.services.security import safe_name

router = APIRouter(prefix="/api/v1", tags=["query"])


# ── Request/Response Schemas ──

class QueryRequest(BaseModel):
    """Request body for POST /api/v1/query."""
    query: str
    kb_name: str
    mode: Optional[Literal["auto", "detailed", "quick"]] = "auto"
    retrieval_pipeline: Optional[Literal["tree", "hybrid", "naive", "combined"]] = "tree"
    session_id: Optional[str] = None
    device_id: Optional[str] = None


class Citation(BaseModel):
    """Citation pointing to source document section."""
    doc_id: str
    page: int = 0
    section: str = ""
    node_id: str = ""


class AgentStep(BaseModel):
    """Individual agent step for transparency."""
    agent: str
    content: str
    timestamp: float


class QueryResponse(BaseModel):
    """Response body for POST /api/v1/query."""
    answer: str
    citations: list[Citation] = []
    agent_steps: list[AgentStep] = []
    model_tier_used: str = ""
    complexity_score: float = 0.0
    e2e_latency_ms: float = 0.0
    session_id: str = ""
    solve_dir: str = ""


# ── Endpoint ──

@router.post("/query", response_model=QueryResponse)
async def http_query(request: QueryRequest):
    """HTTP fallback for Q&A - non-streaming synchronous endpoint."""
    import os
    from app.services.complexity_scorer import score_query_complexity
    from app.routers.retrieval import retrieve, RetrieveRequest

    start_time = time.time()

    # Generate session ID if not provided, sanitize the value to prevent
    # path traversal in ``os.makedirs`` (os.path.join + sanitize_id).
    session_id = request.session_id or f"solve_{int(time.time())}"
    session_id = safe_name(session_id, default=f"solve_{int(time.time())}", max_len=64)
    solve_dir = f"data/user/solve/{session_id}"
    os.makedirs(solve_dir, exist_ok=True)

    # Validate kb_name to prevent path traversal in retrieval pipeline
    request.kb_name = safe_name(request.kb_name, default="default")
    if not request.kb_name:
        raise HTTPException(status_code=400, detail="Invalid kb_name")

    device_id = request.device_id or "default"
    memory_context = ""
    if state.memory_service:
        try:
            from app.services.memory_context import build_memory_context
            recall = await state.memory_service.recall_episodes(device_id, request.query)
            facts = await state.memory_service.recall_facts(device_id, request.query)
            profile = await state.memory_service.get_profile(device_id)
            memory_context = build_memory_context(profile, recall, facts)
        except Exception as e:
            logger.warning(f"Memory recall failed: {e}")

    agent_steps = []

    # ── Step 1: Run retrieval using the same pipeline as WebSocket ──
    agent_steps.append(AgentStep(
        agent="retrieve",
        content=f"Running {request.retrieval_pipeline} retrieval for query: {request.query[:100]}...",
        timestamp=time.time(),
    ))

    retrieve_req = RetrieveRequest(
        query=request.query,
        kb_name=request.kb_name,
        retrieval_pipeline=request.retrieval_pipeline,
        top_k=5,
        min_score=0.3,
    )

    try:
        retrieval_resp = await retrieve(retrieve_req)
        retrieve_results = retrieval_resp.get("results", [])
        retrieved_chunks = len(retrieve_results)
        pipeline_used = retrieval_resp.get("pipeline_used", request.retrieval_pipeline)
    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        retrieve_results = []
        retrieved_chunks = 0
        pipeline_used = "none"

    agent_steps.append(AgentStep(
        agent="retrieve",
        content=f"Retrieved {retrieved_chunks} chunks via {pipeline_used} pipeline",
        timestamp=time.time(),
    ))

    # ── Step 2: Complexity scoring ──
    # Get VRAM status for scoring
    free_vram_mb = float("inf")
    try:
        vram_status = await state.vram_monitor.poll_once()
        total_mb = vram_status.get("vram_total_mb", 0)
        used_mb = vram_status.get("vram_used_mb", 0)
        free_vram_mb = (total_mb - used_mb) if total_mb > 0 else float("inf")
    except Exception:
        pass  # Use infinite if can't get VRAM status

    score, target_tier = score_query_complexity(
        query_text=request.query,
        doc_pages=0,  # TODO: resolve from KB metadata
        retrieved_chunks=retrieved_chunks,
        free_vram_mb=free_vram_mb,
    )

    # ── Step 3: Model selection ──
    model_id = await state.model_manager.get_model_for_tier(target_tier)
    if not model_id:
        model_id = await state.model_manager.get_best_available_model(target_tier)

    model_tier = state.model_manager.get_tier_for_model(model_id) if model_id else target_tier
    model_tier_str = model_id or f"T{model_tier}"

    agent_steps.append(AgentStep(
        agent="route",
        content=f"Complexity score: {score:.3f}, target tier: T{target_tier}, model: {model_id or 'none'}",
        timestamp=time.time(),
    ))

    # ── Step 4: Build context from retrieval results ──
    context_parts = []
    citations = []

    for r in retrieve_results:
        content = r.get("summary", r.get("content", ""))
        context_parts.append(
            f"[{r.get('section', 'Unknown')}] "
            f"(doc:{r.get('doc_id', '')}, p.{r.get('page', 0)}): {content[:500]}"
        )
        citations.append(Citation(
            doc_id=r.get("doc_id", ""),
            page=r.get("page", 0),
            section=r.get("section", ""),
            node_id=r.get("node_id", ""),
        ))

    context = "\n\n".join(context_parts) if context_parts else ""

    # ── Step 5: Generate answer with LLM ──
    answer = ""
    health_ok = await state.lm_client.check_health()

    if health_ok and model_id:
        memory_prefix = f"\n\n{memory_context}\n\n" if memory_context else ""
        system_prompt = (
            "You are an expert document intelligence assistant. "
            + memory_prefix
            + "Provide thorough, well-structured answers based on the provided context. "
            "If the context doesn't contain enough information to answer the query, "
            "state that clearly. Do not invent information not present in the context."
        )

        user_content = f"Query: {request.query}"
        if context:
            user_content += f"\n\nRelevant Context:\n{context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            answer = await state.lm_client.stream_chat(
                messages=messages,
                model=model_id,
                max_tokens=4096,
                priority=3,  # Generation priority
            ) or "No response generated."
            state.model_manager.on_query_start(model_id)
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            answer = f"Error generating answer: {str(e)}"
    else:
        answer = (
            f"LM Studio is not available or no model loaded. "
            f"Query: {request.query}\n"
            f"Retrieved {retrieved_chunks} context sections from {request.kb_name}."
        )

    agent_steps.append(AgentStep(
        agent="solve",
        content=answer[:500],  # Truncate for step log
        timestamp=time.time(),
    ))

    # ── Step 6: Persist session artifacts ──
    try:
        with open(f"{solve_dir}/query_response.md", "w", encoding="utf-8") as f:
            f.write(f"# Query Session: {session_id}\n\n")
            f.write(f"## Query\n{request.query}\n\n")
            f.write(f"## Answer\n{answer}\n\n")
            f.write(f"## Citations\n")
            for c in citations:
                f.write(f"- {c.doc_id} p.{c.page}: {c.section}\n")
    except Exception as e:
        logger.warning(f"Failed to persist session artifacts: {e}")

    if state.memory_service:
        try:
            from app.services.fact_extractor import extract_and_store_facts
            asyncio.create_task(extract_and_store_facts(
                device_id=device_id, query=request.query, answer=answer,
                source_id=session_id, lm_client=state.lm_client, memory_service=state.memory_service,
            ))
            asyncio.create_task(state.memory_service.store_episode(
                device_id=device_id, query=request.query, answer=answer,
                model_used=model_id or "", session_type="query",
            ))
        except Exception:
            pass

    # ── Step 7: Calculate latency and return ──
    e2e_latency_ms = (time.time() - start_time) * 1000

    return QueryResponse(
        answer=answer,
        citations=citations,
        agent_steps=agent_steps,
        model_tier_used=model_tier_str,
        complexity_score=round(score, 3),
        e2e_latency_ms=round(e2e_latency_ms, 1),
        session_id=session_id,
        solve_dir=solve_dir,
    )
