"""System routes: health, config, models, VRAM, cache, metrics."""

import os
import time
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["system"])
settings = get_settings()

METRICS_DIR = Path("data/metrics")
METRICS_DIR.mkdir(parents=True, exist_ok=True)
_metrics_history: list = []


# ── Health ──

@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "lm_studio": False,
        "gpu": False,
        "turboquant_tier": settings.turboquant_tier,
        "message": "Backend stub running — connect LM Studio for full functionality",
    }


# ── Config ──

@router.get("/config")
async def get_config():
    return {
        "llm_host": os.environ.get("LLM_HOST", settings.llm_host),
        "llm_port": int(os.environ.get("LLM_PORT", "1234")),
        "llm_model": os.environ.get("LLM_MODEL", settings.llm_model),
        "embedding_host": os.environ.get("EMBEDDING_HOST", settings.embedding_host),
        "embedding_model": os.environ.get("EMBEDDING_MODEL", settings.embedding_model),
        "turboquant_enabled": settings.turboquant_enabled,
        "turboquant_bits": settings.turboquant_bits,
        "turboquant_tier": settings.turboquant_tier,
        "vram_safety_margin_pct": settings.vram_safety_margin_pct,
        "backend_port": settings.backend_port,
        "frontend_port": settings.frontend_port,
        "search_provider": os.environ.get("SEARCH_PROVIDER", "perplexity"),
    }


@router.put("/config")
async def update_config(payload: dict):
    return {"updated": True}


# ── Models ──

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
async def evict_cache(payload: Optional[dict] = None):
    return {"evicted": True}


# ── Metrics ──

@router.get("/metrics/history")
async def get_metrics_history():
    return _metrics_history


@router.post("/metrics/benchmarks/run")
async def run_benchmarks(payload: Optional[dict] = None):
    return {"run_id": f"bench_{int(time.time())}", "status": "queued"}


@router.get("/metrics/benchmarks/{run_id}")
async def get_benchmark_status(run_id: str):
    return {"run_id": run_id, "status": "pending", "results": {}}
