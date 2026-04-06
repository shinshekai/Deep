"""System routes: health, config, models, VRAM, cache, metrics."""

import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.services.model_manager import MODEL_TIERS

router = APIRouter(prefix="/api/v1", tags=["system"])
settings = get_settings()

METRICS_DIR = Path("data/metrics")
METRICS_DIR.mkdir(parents=True, exist_ok=True)
_metrics_history: list = []

# Simple KV cache state registry — tracks per-model cache info
_cache_state: dict = {}  # model_id -> {cache_type_k, cache_type_v, context_tokens, estimated_size_mb}


# ── Pydantic Schemas ──


class SystemConfigUpdate(BaseModel):
    llm_host: str | None = None
    llm_port: int | None = None
    llm_model: str | None = None
    embedding_host: str | None = None
    embedding_model: str | None = None
    turboquant_enabled: bool | None = None
    turboquant_bits: int | None = None
    turboquant_residual_window: int | None = None
    turboquant_tier: str | None = None
    vram_safety_margin_pct: int | None = None
    backend_port: int | None = None
    frontend_port: int | None = None
    search_provider: str | None = None
    pageindex_model: str | None = None
    t2_ttl: int | None = None
    t3_ttl: int | None = None


class CacheConfigUpdate(BaseModel):
    turboquant_enabled: bool | None = None
    turboquant_bits: int | None = None
    turboquant_tier: str | None = None
    turboquant_residual_window: int | None = None


# ── Health ──


@router.get("/health")
async def health_check():
    from app.main import vram_monitor, lm_client

    # Check LM Studio
    lm_available = await lm_client.check_health()

    # Check GPU / VRAM
    vram_data = await vram_monitor.poll_once()
    gpu_available = vram_data.get("gpu_available", False)

    # Calculate uptime from module-level startup time
    try:
        from app.main import _startup_time
        uptime = time.time() - _startup_time
    except Exception:
        uptime = 0

    return {
        "status": "ok" if (lm_available and gpu_available) else "degraded",
        "lm_studio": lm_available,
        "gpu": gpu_available,
        "turboquant_tier": settings.turboquant_tier,
        "turboquant_enabled": settings.turboquant_enabled,
        "uptime_seconds": round(uptime, 1),
        "vram_used_pct": vram_data.get("vram_used_pct", 0),
        "active_models_count": len(_cache_state),
        "message": _health_message(lm_available, gpu_available),
    }


def _health_message(lm: bool, gpu: bool) -> str:
    if lm and gpu:
        return "All systems operational."
    if lm:
        return "LM Studio connected but GPU unavailable."
    if gpu:
        return "GPU available but LM Studio not reachable."
    return "Backend running — connect LM Studio and GPU for full functionality."


# ── Config ──


@router.get("/config")
async def get_config():
    return {
        "llm_host": settings.llm_host,
        "llm_port": settings.llm_port,
        "llm_model": settings.llm_model,
        "embedding_host": settings.embedding_host,
        "embedding_model": settings.embedding_model,
        "turboquant_enabled": settings.turboquant_enabled,
        "turboquant_bits": settings.turboquant_bits,
        "turboquant_tier": settings.turboquant_tier,
        "turboquant_residual_window": settings.turboquant_residual_window,
        "vram_safety_margin_pct": settings.vram_safety_margin_pct,
        "backend_port": settings.backend_port,
        "frontend_port": settings.frontend_port,
        "search_provider": os.environ.get("SEARCH_PROVIDER", "perplexity"),
        "pageindex_model": settings.pageindex_model,
        "t2_ttl": settings.t2_ttl,
        "t3_ttl": settings.t3_ttl,
    }


@router.put("/config")
async def update_config(payload: SystemConfigUpdate):
    """Update runtime configuration. Only provided fields are updated."""
    import os

    data = payload.model_dump(exclude_unset=True)
    updates = []

    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
            updates.append(key)

            # Persist known env vars back to environment (so child processes see them)
            env_key = key.upper()
            os.environ[env_key] = str(value)

    # Clear the lru cache on get_settings so future calls return updated settings
    get_settings.cache_clear()

    return {
        "updated": len(updates) > 0,
        "fields_updated": updates,
        **{k: getattr(settings, k, None) for k in updates},
    }


# ── Models ──


@router.get("/models")
async def list_models():
    from app.main import lm_client, model_manager

    # Get models from LM Studio
    lm_models = await lm_client.list_models()
    lm_model_ids = {m.get("id", m.get("name", "")) for m in lm_models}

    # Build response enriched with manager data
    loaded = model_manager._loaded_models
    tier_info = {}

    for tier_num, tier_data in MODEL_TIERS.items():
        for mid in tier_data.get("models", []):
            tier_info[mid] = tier_data

    result = []

    # All known models (from LM Studio + manager)
    all_ids = lm_model_ids | set(loaded.keys())

    for mid in sorted(all_ids):
        tier = model_manager.get_tier_for_model(mid) or 0
        is_loaded = mid in loaded
        loaded_info = loaded.get(mid, {})
        kv = tier_info.get(mid, {}).get("kv_cache", {})

        result.append({
            "id": mid,
            "name": mid,
            "tier": tier,
            "status": "loaded" if is_loaded else "available",
            "vram_used_mb": loaded_info.get("vram_mb", 0),
            "loaded_at": loaded_info.get("loaded_at"),
            "last_used": loaded_info.get("last_used"),
            "kv_cache_config": kv,
        })

    # If no models found, return tier defaults as available
    if not result:
        result = model_manager.get_status()

    return result


@router.post("/models/{model_id}/load")
async def load_model(model_id: str):
    from app.main import lm_client, model_manager

    success = await lm_client.load_model(model_id)

    if success:
        tier = model_manager.get_tier_for_model(model_id) or 1
        model_manager._loaded_models[model_id] = {
            "tier": tier,
            "loaded_at": time.time(),
            "last_used": time.time(),
        }

    return {
        "model_id": model_id,
        "status": "loaded" if success else "failed",
        "tier": model_manager.get_tier_for_model(model_id),
    }


@router.post("/models/{model_id}/unload")
async def unload_model(model_id: str):
    from app.main import lm_client, model_manager

    success = await lm_client.unload_model(model_id)

    if success and model_id in model_manager._loaded_models:
        del model_manager._loaded_models[model_id]

    return {
        "model_id": model_id,
        "status": "unloaded" if success else "failed",
    }


# ── VRAM ──


@router.get("/vram/status")
async def get_vram_status():
    from app.main import vram_monitor

    data = await vram_monitor.poll_once()

    total = data.get("vram_total_mb", 0)
    used = data.get("vram_used_mb", 0)
    free = max(0, total - used)

    # Build a basic breakdown showing tier-level estimates
    breakdown = {}
    if data.get("gpu_available"):
        breakdown = {
            "total_gpu_memory_mb": round(total, 1),
            "used_gpu_memory_mb": round(used, 1),
            "free_gpu_memory_mb": round(free, 1),
            "gpu_utilization_pct": round(data.get("vram_used_pct", 0), 1),
        }

    return {
        "total_mb": round(total, 1),
        "used_mb": round(used, 1),
        "free_mb": round(free, 1),
        "utilization_pct": round(data.get("vram_used_pct", 0), 1),
        "pressure_level": data.get("pressure_level", "green"),
        "gpu_available": data.get("gpu_available", False),
        "breakdown": breakdown,
    }


# ── Cache ──


@router.get("/cache/status")
async def cache_status():
    from app.main import model_manager

    s = settings
    models_info = {}

    for model_id, info in model_manager._loaded_models.items():
        tier = info.get("tier", 1)
        kv = model_manager.get_kv_config(tier)
        cache_entry = _cache_state.get(model_id, {})

        models_info[model_id] = {
            "tier": tier,
            "cache_type_k": kv.get("cache_type_k", "f16"),
            "cache_type_v": kv.get("cache_type_v", "f16"),
            "context_tokens": cache_entry.get("context_tokens", 0),
            "estimated_size_mb": cache_entry.get("estimated_size_mb", 0),
        }

    return {
        "turboquant_enabled": s.turboquant_enabled,
        "turboquant_bits": s.turboquant_bits,
        "turboquant_tier": s.turboquant_tier,
        "turboquant_residual_window": s.turboquant_residual_window,
        "models": models_info,
        "tracked_entries": len(_cache_state),
    }


@router.put("/cache/config")
async def update_cache_config(payload: CacheConfigUpdate):
    data = payload.model_dump(exclude_unset=True)

    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    return {
        "updated": True,
        "config": {
            "turboquant_enabled": settings.turboquant_enabled,
            "turboquant_bits": settings.turboquant_bits,
            "turboquant_tier": settings.turboquant_tier,
            "turboquant_residual_window": settings.turboquant_residual_window,
        },
    }


@router.post("/cache/evict")
async def evict_cache(payload: Optional[dict] = None):
    model_id = payload.get("model_id") if payload else None

    if model_id and model_id in _cache_state:
        freed = _cache_state[model_id].get("estimated_size_mb", 0)
        del _cache_state[model_id]
        return {"evicted": True, "model_id": model_id, "freed_mb": freed}

    # Evict all non-pinned cache entries
    count = len(_cache_state)
    _cache_state.clear()
    return {"evicted": True, "entries_cleared": count}


# ── Metrics ──


@router.get("/metrics/history")
async def get_metrics_history():
    return _metrics_history


@router.post("/metrics/benchmarks/run")
async def run_benchmarks(payload: Optional[dict] = None):
    from app.main import benchmark_runner
    category = "all"
    if payload and "category" in payload:
        category = payload["category"]
    if category not in ("all", "latency", "kv_cache", "quality", "throughput"):
        return {"error": f"Unknown category: {category}. Valid: all, latency, kv_cache, quality, throughput"}
    run_id = await benchmark_runner.start_run(category)
    return {"run_id": run_id, "category": category, "status": "queued"}


@router.get("/metrics/benchmarks/{run_id}")
async def get_benchmark_status(run_id: str):
    from app.main import benchmark_runner
    run = benchmark_runner.get_run(run_id)
    if run is None:
        return {"run_id": run_id, "status": "not_found"}
    return {
        "run_id": run.run_id,
        "category": run.category,
        "status": run.status,
        "progress_pct": run.progress_pct,
        "error": run.error,
        "results": [
            {
                "test_id": r.test_id,
                "category": r.category,
                "test_case": r.test_case,
                "metric": r.metric,
                "value": r.value,
                "threshold": r.threshold,
                "passed": r.passed,
            }
            for r in run.results
        ],
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.get("/metrics/benchmarks/latest")
async def get_latest_benchmark():
    from app.main import benchmark_runner
    run = benchmark_runner.get_latest_run()
    if run is None:
        return {"status": "no_runs"}
    return {
        "run_id": run.run_id,
        "category": run.category,
        "status": run.status,
        "progress_pct": run.progress_pct,
        "error": run.error,
        "results": [
            {
                "test_id": r.test_id,
                "category": r.category,
                "test_case": r.test_case,
                "metric": r.metric,
                "value": r.value,
                "threshold": r.threshold,
                "passed": r.passed,
            }
            for r in run.results
        ],
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


