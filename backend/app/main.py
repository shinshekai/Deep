"""UDIP Backend — FastAPI application entry point.

Services: VRAMMonitor, LMStudioClient, ModelManager, EmbeddingService,
          TextChunker, VectorKBService
Routers: knowledge, system, agent, retrieval, query
WebSockets: /api/v1/solve (Smart Solve dual-loop), /ws/metrics (broadcast)
"""

import asyncio
import json
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    # Set up basic tracer provider
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None

from app.config import get_settings
from app.state import (
    vram_monitor, lm_client, model_manager, pageindex_generator,
    benchmark_runner, embedding_service, text_chunker, vector_kb_service,
    update_metrics, add_ws, remove_ws, get_ws_set, get_metrics,
)

logger = logging.getLogger(__name__)

settings = get_settings()

# Services are initialized in lifespan()
_startup_time: float = 0.0

# Metrics history for system router
_metrics_history: list = []
METRICS_DIR = "data/metrics"
import os
from pathlib import Path
os.makedirs(METRICS_DIR, exist_ok=True)


# ─── Lifespan ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_time
    _startup_time = time.time()
    logger.info("Starting UDIP Backend on :8001")

    # Initialize services
    from app.services.vram_monitor import VRAMMonitor
    from app.services.lm_studio_client import LMStudioClient
    from app.services.model_manager import ModelManager
    from app.services.pageindex_generator import PageIndexTreeGenerator
    from app.services.benchmark_runner import BenchmarkRunner
    from app.services.embedding_service import EmbeddingService
    from app.services.text_chunker import TextChunker
    from app.services.vector_kb import VectorKBService

    # Create service instances and update shared state
    from app import state

    state.vram_monitor = VRAMMonitor()
    state.lm_client = LMStudioClient(metrics_callback=update_metrics)
    state.model_manager = ModelManager(state.lm_client)
    state.pageindex_generator = PageIndexTreeGenerator(state.lm_client)
    state.benchmark_runner = BenchmarkRunner(state.lm_client, state.vram_monitor, state.model_manager)
    state.embedding_service = EmbeddingService(state.lm_client, batch_size=32)
    from app.services.deep_research import DeepResearchService
    
    state.text_chunker = TextChunker(chunk_size=512, chunk_overlap=64)
    state.deep_research_service = DeepResearchService(lm_client=state.lm_client)

    _KB_BASE = Path("data/knowledge_bases")
    state.vector_kb_service = VectorKBService(kb_base=_KB_BASE, lm_client=state.lm_client)

    # Initialize VRAM monitor
    gpu_ok = await vram_monitor.initialize()
    logger.info(f"GPU monitor: {'active' if gpu_ok else 'unavailable (no pynvml)'}")

    lm_ok = await lm_client.check_health()
    logger.info(f"LM Studio: {'connected' if lm_ok else 'not reachable'}")

    if lm_ok:
        models = await lm_client.list_models()
        for m in models:
            mid = m.get("id", m.get("name", "unknown"))
            tier = model_manager.get_tier_for_model(mid) or 1
            model_manager._loaded_models[mid] = {
                "tier": tier, "loaded_at": time.time(), "last_used": time.time(),
            }
            logger.info(f"Model registered: {mid} (tier {tier})")

    def on_vram(data: dict):
        from app.state import _latest_metrics
        _latest_metrics["vram_used_mb"] = data.get("vram_used_mb", 0)
        _latest_metrics["vram_total_mb"] = data.get("vram_total_mb", 0)
        _latest_metrics["pressure_level"] = data.get("pressure_level", "green")

    vram_monitor.on_update(on_vram)

    await benchmark_runner.start_worker()

    vram_task = asyncio.create_task(vram_monitor.start_polling(interval=2.0))
    broadcast_task = asyncio.create_task(_broadcast_loop())
    ttl_task = asyncio.create_task(_ttl_loop())

    yield

    vram_task.cancel()
    broadcast_task.cancel()
    ttl_task.cancel()
    logger.info("Shutdown complete.")


async def _broadcast_loop():
    """Broadcast metrics every 2s to /ws/metrics subscribers."""
    while True:
        await asyncio.sleep(2.0)
        from app.state import _latest_metrics, _metrics_ws
        dead = []
        for ws in list(_metrics_ws):
            try:
                await ws.send_json(dict(_latest_metrics))
            except Exception:
                dead.append(ws)
        for ws in dead:
            _metrics_ws.discard(ws)
        _metrics_history.append(dict(_latest_metrics))
        if len(_metrics_history) > 30:
            _metrics_history = _metrics_history[-30:]
        from app.routers import system as sm
        sm._metrics_history = _metrics_history


async def _ttl_loop():
    while True:
        await asyncio.sleep(60)
        from app.state import model_manager
        evicted = model_manager.check_ttl_evictions()
        if evicted:
            logger.info(f"TTL evictions: {evicted}")


# ─── App ───

app = FastAPI(
    title="UDIP Backend",
    description="Unified Document Intelligence Pipeline — FastAPI backend",
    version="0.1.0",
    lifespan=lifespan,
)

if tracer:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3782", "http://127.0.0.1:3782", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import Request

@app.middleware("http")
async def benchmark_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    elapsed_ms = (time.time() - start_time) * 1000
    from app.state import _latest_metrics
    _latest_metrics["latency_ms"] = int(elapsed_ms)
    response.headers["X-E2E-Latency-ms"] = str(round(elapsed_ms, 2))
    return response


# Import routers after middleware setup
from app.routers.knowledge import router as knowledge_router
from app.routers.system import router as system_router
from app.routers.agent import router as agent_router
from app.routers.retrieval import router as retrieval_router
from app.routers.query import router as query_router
from app.validation.validation_routes import router as validation_router

app.include_router(knowledge_router)
app.include_router(system_router)
app.include_router(agent_router)
app.include_router(retrieval_router)
app.include_router(query_router)
app.include_router(validation_router)


# ─── Smart Solve WS ───

@app.websocket("/api/v1/solve")
async def ws_solve(ws: WebSocket):
    from app.config import get_settings
    settings = get_settings()
    token = ws.query_params.get("token")
    if settings.ws_auth_token and token != settings.ws_auth_token:
        await ws.close(code=1008, reason="Unauthorized")
        return

    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            query = data.get("query", "")
            if not query.strip():
                await ws.send_json({"type": "error", "error": "empty_query", "message": "Query cannot be empty."})
                continue

            session_id = data.get("session_id", f"solve_{int(time.time())}")
            kb_name = data.get("kb_name", "")
            mode = data.get("mode", "auto")
            retrieval_pipeline = data.get("retrieval_pipeline", "tree")

            await ws.send_json({
                "type": "agent_step", "agent": "investigate",
                "content": f"Analyzing query: {query[:100]}...", "timestamp": time.time(),
            })
            await asyncio.sleep(0.4)

            from app.state import lm_client, model_manager
            lm_ok = await lm_client.check_health()
            if lm_ok:
                from app.services.solve_orchestrator import run_solve_pipeline
                from app.services.recursive_solver import RecursiveSolver
                
                # Check if recursive mode is requested explicitly, or if auto mode selects it
                if mode == "recursive" or (mode == "auto" and "recursive" in query.lower()):
                    solver = RecursiveSolver(lm_client)
                    # Use complexity scorer to select pattern
                    from app.services.complexity_scorer import score_query_complexity
                    score, _ = score_query_complexity(query)
                    pattern = solver.select_pattern(query, score)
                    
                    await ws.send_json({
                        "type": "agent_step", "agent": "system",
                        "content": f"[RecursiveMAS Activated: {pattern} pattern]\n", "timestamp": time.time(),
                    })
                    
                    # Optional: retrieve context first if kb_name provided
                    context = ""
                    if kb_name:
                        from app.routers.retrieval import retrieve as run_retrieval, RetrieveRequest
                        req = RetrieveRequest(query=query, kb_name=kb_name, retrieval_pipeline=retrieval_pipeline, top_k=3)
                        retrieval_resp = await run_retrieval(req)
                        rag_results = retrieval_resp.get("results", [])
                        if rag_results:
                            for i, res in enumerate(rag_results):
                                context += f"--- Chunk {i+1} ---\n{res.get('content', '')}\n\n"
                                
                    model_id = await model_manager.get_best_available_model() or "Qwen3-1.7B-Q4_K_M"
                    result = await solver.solve(
                        query=query,
                        context=context,
                        pattern=pattern,
                        model_id=model_id,
                        ws_send=ws.send_json
                    )
                    
                    await ws.send_json({
                        "type": "complete",
                        "answer": result.answer,
                        "citations": [],
                        "session_id": session_id,
                        "solve_dir": f"data/user/solve/{session_id}",
                        "metadata": {
                            "pattern": result.pattern,
                            "rounds_used": result.rounds_used,
                            "converged": result.converged,
                            "token_savings_pct": result.token_savings_pct,
                            "elapsed_seconds": result.elapsed_seconds,
                        }
                    })
                else:
                    await run_solve_pipeline(
                        query=query,
                        kb_name=kb_name,
                        mode=mode,
                        retrieval_pipeline=retrieval_pipeline,
                        lm_client=lm_client,
                        model_manager=model_manager,
                        session_id=session_id,
                        ws_send=ws.send_json,
                    )
                continue

            # Fallback: simulated agent steps
            steps = [
                ("note", f"No knowledge base loaded. Query: {query[:80]}"),
                ("plan", "Structuring response..."),
                ("solve", "Generating answer..."),
                ("check", "Validating accuracy..."),
                ("format", "Polishing output..."),
            ]
            full_answer = ""
            for label, content in steps:
                await ws.send_json({
                    "type": "agent_step", "agent": label,
                    "content": content, "timestamp": time.time(),
                })
                await asyncio.sleep(0.3)
                full_answer += f"{content}\n\n"

            await ws.send_json({
                "type": "complete",
                "answer": full_answer.strip() + "\n\n— *Connect LM Studio at localhost:1234 for real multi-agent reasoning.*",
                "citations": [], "session_id": session_id,
                "solve_dir": f"data/user/solve/{session_id}",
            })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Solve WS error: {e}", exc_info=True)


# ─── Metrics WS ───

@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
    from app.config import get_settings
    settings = get_settings()
    token = ws.query_params.get("token")
    if settings.ws_auth_token and token != settings.ws_auth_token:
        await ws.close(code=1008, reason="Unauthorized")
        return

    await ws.accept()
    from app.state import add_ws
    add_ws(ws)
    try:
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        from app.state import remove_ws
        remove_ws(ws)
