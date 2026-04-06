import json
import os
import time
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

# Active WebSocket metrics subscribers
metrics_subscribers: set[WebSocket] = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start metrics broadcast task
    task = asyncio.create_task(_metrics_broadcast_loop())
    yield
    task.cancel()

async def _metrics_broadcast_loop():
    """Broadcast metrics to /ws/metrics subscribers every 2 seconds."""
    interval = settings.metrics_interval
    import json, time
    while True:
        await asyncio.sleep(interval)
        frame = {
            "vram_used_mb": 0,
            "vram_total_mb": 0,
            "pressure_level": "green",
            "active_models": [],
            "queue_depths": {"retrieval": 0, "reasoning": 0, "generation": 0},
            "latency_ms": 0,
            "throughput_tps": 0,
        }
        # Broadcast to all connected metrics subscribers
        dead = []
        for ws in list(metrics_subscribers):
            try:
                await ws.send_json(frame)
            except Exception:
                dead.append(ws)
        for ws in dead:
            metrics_subscribers.discard(ws)

app = FastAPI(
    title="UDIP Backend",
    description="Unified Document Intelligence Pipeline — FastAPI backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3782", "http://127.0.0.1:3782"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────
# API Router
# ──────────────────────────────────────────

from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional

router = APIRouter(prefix="/api/v1")

# ── Knowledge Base Endpoints ──

@router.post("/knowledge/upload")
async def upload_document(
    file: UploadFile = File(...),
    kb_name: str = Form("default"),
    chunk_size: int = Form(512),
    chunk_overlap: int = Form(64),
):
    return {"task_id": f"task_{int(time.time())}", "status": "processing"}

@router.get("/knowledge/tasks/{task_id}")
async def get_task_status(task_id: str):
    return {
        "task_id": task_id,
        "status": "complete",
        "progress": 100,
        "message": "Backend not fully implemented — stub response",
        "doc_id": f"doc_{task_id}",
    }

@router.get("/knowledge/bases")
async def list_knowledge_bases():
    return []

@router.get("/knowledge/bases/{kb_name}")
async def get_knowledge_base(kb_name: str):
    return {"name": kb_name, "status": "active", "total_pages": 0, "total_docs": 0, "created_at": ""}

@router.delete("/knowledge/bases/{kb_name}")
async def delete_knowledge_base(kb_name: str):
    return {"deleted": True, "kb_name": kb_name}

@router.get("/knowledge/bases/{kb_name}/pageindex/{doc_id}")
async def get_pageindex_tree(kb_name: str, doc_id: str):
    return {"doc_id": doc_id, "tree": {"node_id": "root", "title": "Root", "summary": "", "children": []}}

# ── Query / Retrieve ──

@router.post("/query")
async def query(query: dict):
    return {"answer": "Stub response. Backend not fully implemented.", "citations": []}

@router.post("/retrieve")
async def retrieve(query: dict):
    return {"results": [], "total": 0}

# ── Deep Research ──

@router.post("/research")
async def start_research(payload: dict):
    return {"session_id": f"research_{int(time.time())}", "status": "queued"}

# ── Question Generator ──

@router.post("/questions/generate")
async def generate_questions(payload: dict):
    return {"questions": [], "total": 0}

# ── Guided Learning ──

@router.post("/learning/start")
async def start_learning(payload: dict):
    return {"session_id": f"learn_{int(time.time())}", "status": "active"}

# ── Model Management ──

@router.get("/models")
async def list_models():
    return []

@router.post("/models/{model_id}/load")
async def load_model(model_id: str):
    return {"model_id": model_id, "status": "loading"}

@router.post("/models/{model_id}/unload")
async def unload_model(model_id: str):
    return {"model_id": model_id, "status": "unloaded"}

# ── VRAM ──

@router.get("/vram/status")
async def get_vram_status():
    return {
        "vram_total_mb": 0,
        "vram_used_mb": 0,
        "vram_used_pct": 0,
        "pressure_level": "green",
    }

# ── Cache ──

@router.get("/cache/status")
async def cache_status():
    return {"models": {}}

@router.put("/cache/config")
async def update_cache_config(payload: dict):
    return {"updated": True}

@router.post("/cache/evict")
async def evict_cache(payload: dict = None):
    return {"evicted": True}

# ── Metrics ──

@router.get("/metrics/history")
async def get_metrics_history():
    return []

@router.post("/metrics/benchmarks/run")
async def run_benchmarks(payload: dict = None):
    return {"run_id": f"bench_{int(time.time())}", "status": "queued"}

@router.get("/metrics/benchmarks/{run_id}")
async def get_benchmark_status(run_id: str):
    return {"run_id": run_id, "status": "pending", "results": {}}

# ── Health ──

@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "lm_studio": False,
        "gpu": False,
        "turboquant_tier": "auto",
        "message": "Backend stub running — connect LM Studio for full functionality",
    }

# ── Config ──

@router.get("/config")
async def get_config():
    return {
        "llm_host": os.environ.get("LLM_HOST", ""),
        "llm_port": int(os.environ.get("LLM_PORT", "1234")),
        "llm_api_key": "..." if os.environ.get("LLM_API_KEY") else "",
        "backend_port": settings.backend_port,
        "frontend_port": settings.frontend_port,
    }

@router.put("/config")
async def update_config(payload: dict):
    return {"updated": True}

app.include_router(router)

# ─── WebSocket Endpoints ───

@app.websocket("/api/v1/solve")
async def ws_solve(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("query", "")
            session_id = data.get("session_id", f"session_{int(time.time())}")

            # Stream stub: send a few agent steps, then a placeholder answer
            steps = [
                {"type": "agent_step", "agent": "investigate", "content": f"Analyzing query: {query[:80]}...", "timestamp": time.time()},
                {"type": "agent_step", "agent": "note", "content": "Context retrieved from knowledge base (stub — no KB loaded).", "timestamp": time.time()},
                {"type": "agent_step", "agent": "plan", "content": "Planning response approach...", "timestamp": time.time()},
                {"type": "agent_step", "agent": "solve", "content": "Synthesizing answer...", "timestamp": time.time()},
                {"type": "agent_step", "agent": "check", "content": "Validating response quality...", "timestamp": time.time()},
                {"type": "agent_step", "agent": "format", "content": "Formatting output...", "timestamp": time.time()},
            ]
            for step in steps:
                await websocket.send_json(step)
                await asyncio.sleep(0.3)

            await websocket.send_json({
                "type": "complete",
                "answer": f"Backend stub: received query \"{query}\". Connect the full backend pipeline for real multi-agent reasoning.",
                "citations": [],
                "session_id": session_id,
                "solve_dir": f"data/user/solve/{session_id}",
            })
    except WebSocketDisconnect:
        pass

@app.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    await websocket.accept()
    metrics_subscribers.add(websocket)
    try:
        while True:
            # Keep connection alive — wait for disconnect
            data = await websocket.receive_text()
            # Acknowledge
            await websocket.send_json({"ack": True, "received": data})
    except WebSocketDisconnect:
        pass
    finally:
        metrics_subscribers.discard(websocket)
