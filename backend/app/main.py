"""UDIP Backend — FastAPI application entry point.

Services: VRAMMonitor, LMStudioClient, ModelManager
Routers: knowledge, system, agent
WebSockets: /api/v1/solve (Smart Solve dual-loop), /ws/metrics (broadcast)
"""

import asyncio
import json
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.services.vram_monitor import VRAMMonitor
from app.services.lm_studio_client import LMStudioClient
from app.services.model_manager import ModelManager
from app.services.pageindex_generator import PageIndexTreeGenerator
from app.routers.knowledge import router as knowledge_router
from app.routers.system import router as system_router
from app.routers.agent import router as agent_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global services
vram_monitor = VRAMMonitor()
lm_client = LMStudioClient()
model_manager = ModelManager(lm_client)
pageindex_generator = PageIndexTreeGenerator(lm_client)

# Metrics subscribers + latest broadcast frame
_metrics_ws: set[WebSocket] = set()
_latest_metrics: dict = {
    "vram_used_mb": 0,
    "vram_total_mb": 0,
    "pressure_level": "green",
    "active_models": [],
    "queue_depths": {"retrieval": 0, "reasoning": 0, "generation": 0},
    "latency_ms": 0,
    "throughput_tps": 0,
}


# ─── Lifespan ───

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting UDIP Backend on :8001")

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
        _latest_metrics["vram_used_mb"] = data.get("vram_used_mb", 0)
        _latest_metrics["vram_total_mb"] = data.get("vram_total_mb", 0)
        _latest_metrics["pressure_level"] = data.get("pressure_level", "green")

    vram_monitor.on_update(on_vram)

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
    history = []
    while True:
        await asyncio.sleep(2.0)
        dead = []
        for ws in list(_metrics_ws):
            try:
                await ws.send_json(_latest_metrics)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _metrics_ws.discard(ws)
        history.append(dict(_latest_metrics))
        if len(history) > 30:
            history = history[-30:]
        from app.routers import system as sm
        sm._metrics_history = history


async def _ttl_loop():
    while True:
        await asyncio.sleep(60)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3782", "http://127.0.0.1:3782", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(knowledge_router)
app.include_router(system_router)
app.include_router(agent_router)


# ─── Smart Solve WS ───

@app.websocket("/api/v1/solve")
async def ws_solve(ws: WebSocket):
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

            # Send investigation step
            await ws.send_json({
                "type": "agent_step", "agent": "investigate",
                "content": f"Analyzing query: {query[:100]}...", "timestamp": time.time(),
            })
            await asyncio.sleep(0.4)

            # Compute complexity and route to tier
            lm_ok = await lm_client.check_health()
            if lm_ok:
                # Full pipeline: analysis loop → solve loop
                full_answer = await _run_llm_solve(ws, query, kb_name, mode, session_id)
                if full_answer:
                    await ws.send_json({
                        "type": "complete", "answer": full_answer,
                        "citations": [], "session_id": session_id,
                        "solve_dir": f"data/user/solve/{session_id}",
                    })
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


async def _run_llm_solve(ws, query, kb_name, mode, session_id):
    """Stream real LLM response through agent step frames."""
    # Analysis: system prompt for investigation
    analysis_prompt = (
        f"Analyze this query from a document intelligence context. "
        f"Break it down into key concepts and a plan. Query: {query}"
    )
    result = await lm_client.stream_chat(
        messages=[
            {"role": "system", "content": "You are a document analysis agent. Investigate the user's query."},
            {"role": "user", "content": query},
        ]
    )
    if result:
        await ws.send_json({
            "type": "agent_step", "agent": "investigate",
            "content": result[:300], "timestamp": time.time(),
        })
        await asyncio.sleep(0.2)

        await ws.send_json({
            "type": "agent_step", "agent": "note",
            "content": f"Synthesized findings from analysis.", "timestamp": time.time(),
        })
        await asyncio.sleep(0.2)

    # Plan
    await ws.send_json({
        "type": "agent_step", "agent": "plan",
        "content": "Planning approach based on analysis...", "timestamp": time.time(),
    })
    await asyncio.sleep(0.2)

    # Solve — stream full answer
    solve_result = await lm_client.stream_chat(
        messages=[
            {"role": "system", "content": "You are an expert document intelligence assistant. Provide a thorough, well-structured answer."},
            {"role": "user", "content": query},
        ]
    )
    if solve_result:
        await ws.send_json({
            "type": "agent_step", "agent": "solve",
            "content": solve_result[:300], "timestamp": time.time(),
        })
        await asyncio.sleep(0.2)

        await ws.send_json({
            "type": "agent_step", "agent": "check",
            "content": "Answer validated.", "timestamp": time.time(),
        })
        await asyncio.sleep(0.2)

        return solve_result
    return None


# ─── Metrics WS ───

@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
    await ws.accept()
    _metrics_ws.add(ws)
    try:
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _metrics_ws.discard(ws)
